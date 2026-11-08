import hashlib
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.ingestion.manifest import ManifestManager


def safe_filename(name: str) -> str:
    """Chuyển tên file về dạng an toàn."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name.strip(" .")


class DocumentCollector:

    def __init__(
        self,
        output_dir: str,
        manifest_path: str = "data/manifests/ingestion_manifest.json",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = ManifestManager(manifest_path)

        # Khởi tạo HTTP Session với User-Agent giả lập trình duyệt thật
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })

        retry_strategy = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET"]),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    @staticmethod
    def calculate_checksum(file_path: Path) -> str:
        """Tính mã SHA256 của file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def detect_extension(url: str, content_type: str, content: bytes) -> str:
        """Xác định định dạng dựa trên nội dung thực tế."""
        url_path = urlparse(url).path.lower()
        content_start = content[:1000].lstrip().lower()

        if content.startswith(b"%PDF-"):
            return ".pdf"

        is_html = (
            "text/html" in content_type
            or "application/xhtml+xml" in content_type
            or content_start.startswith(b"<!doctype html")
            or content_start.startswith(b"<html")
            or b"<html" in content_start
        )
        if is_html:
            return ".html"

        if url_path.endswith(".txt") or "text/plain" in content_type or "application/json" in content_type:
            return ".txt"

        raise ValueError(f"Không nhận diện được định dạng tài liệu. Content-Type: {content_type}")

    @staticmethod
    def validate_content(content: bytes, extension: str) -> None:
        """Kiểm tra nội dung thực tế trước khi lưu."""
        if not content or not content.strip():
            raise ValueError("Response rỗng.")

        if extension == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise ValueError("File không có chữ ký PDF hợp lệ.")
            return

        if extension == ".html":
            html_lower = content[:50000].lower()
            blocked_markers = [
                b"awswaf", b"awswafintegration", b"challenge.js",
                b"challenge-container", b"gokuprops", b"captcha",
                b"token.awswaf.com", b"request blocked", b"robot check",
            ]
            for marker in blocked_markers:
                if marker in html_lower:
                    raise ValueError(
                        "Nguồn trả về trang chống bot/xác minh truy cập. "
                        f"Phát hiện: {marker.decode('utf-8', errors='replace')}"
                    )

            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)

            redirect_messages = [
                "you are being redirected", "redirecting you",
                "please wait while you are redirected", "please wait while we redirect",
                "redirecting...",
            ]
            if any(message in text.lower() for message in redirect_messages):
                raise ValueError("Nguồn chỉ trả về trang chuyển hướng, không phải nội dung tài liệu.")
            if len(text) < 100:
                raise ValueError(f"Nội dung HTML quá ngắn ({len(text)} ký tự).")

        elif extension == ".txt":
            if len(content.strip()) < 100:
                raise ValueError("Nội dung TXT quá ngắn.")

    def fetch_via_official_api(self, url: str):
        """
        Gọi REST API chính thức đối với nguồn US Federal Register hoặc EUR-Lex CELLAR
        để tránh bị chặn bởi Captcha / AWS WAF.
        """
        # 1. US Federal Register REST API (ví dụ: 2023-24283 cho EO 14110)
        fed_match = re.search(r"federalregister\.gov/documents/\d{4}/\d{2}/\d{2}/([\d-]+)", url)
        if fed_match:
            doc_num = fed_match.group(1)
            api_url = f"https://www.federalregister.gov/api/v1/documents/{doc_num}.json"
            resp = self.session.get(api_url, timeout=(10, 30))
            if resp.ok:
                meta = resp.json()
                body_html_url = meta.get("body_html_url") or meta.get("full_text_xml_url")
                if body_html_url:
                    body_resp = self.session.get(body_html_url, timeout=(10, 60))
                    if body_resp.ok and len(body_resp.content) > 200:
                        return body_resp.content, "text/html", body_html_url

        # 2. EUR-Lex CELLAR REST API (tránh AWS WAF trên eur-lex.europa.eu)
        if "eur-lex.europa.eu" in url and ("2024/1689" in url or "202401689" in url):
            cellar_url = "https://publications.europa.eu/resource/celex/32024R1689.ENG.xhtml"
            headers = {"Accept": "application/xhtml+xml, text/html;q=0.9"}
            resp = self.session.get(cellar_url, headers=headers, timeout=(10, 60), allow_redirects=True)
            if resp.ok and len(resp.content) > 1000 and b"awswaf" not in resp.content[:10000].lower():
                return resp.content, "text/html", resp.url

        return None

    def download_content(self, url: str):
        """Tải nội dung từ URL (ưu tiên API chính thức nếu có)."""
        api_result = None
        try:
            api_result = self.fetch_via_official_api(url)
        except Exception:
            api_result = None

        if api_result is not None:
            return api_result

        response = self.session.get(url, timeout=(10, 60), allow_redirects=True)
        response.raise_for_status()
        content = response.content
        if not content:
            raise ValueError("Server trả về response rỗng.")
        content_type = response.headers.get("Content-Type", "").lower()
        return content, content_type, response.url

    def collect_one(self, document: dict) -> dict:
        """Thu thập một tài liệu và cập nhật Manifest."""
        document_id = document["document_id"]
        url = (document.get("download_url") or "").strip() or (document.get("source_url") or "").strip()

        file_path = None
        temp_path = None

        try:
            content, content_type, final_url = self.download_content(url)
            extension = self.detect_extension(final_url, content_type, content)
            self.validate_content(content, extension)

            filename = safe_filename(document_id + extension)
            file_path = self.output_dir / filename
            temp_path = file_path.with_name(file_path.name + ".tmp")

            try:
                with open(temp_path, "wb") as file:
                    file.write(content)
                if not temp_path.exists() or temp_path.stat().st_size == 0:
                    raise ValueError("File tải xuống bị rỗng.")
                temp_path.replace(file_path)
            finally:
                if temp_path and temp_path.exists():
                    temp_path.unlink()

            checksum = self.calculate_checksum(file_path)
            self.manifest.update(
                document_id,
                status="downloaded",
                checksum=checksum,
                file_path=str(file_path),
                source_url=document.get("source_url") or url,
                final_url=final_url,
                content_type=content_type,
                file_size=len(content),
                title=document.get("title", ""),
                region=document.get("jurisdiction", ""),
                document_type=document.get("doc_type", ""),
                language=document.get("language", ""),
                published_date=document.get("published_date", ""),
                error=None,
                parse_error=None,
            )

            return {
                "document_id": document_id,
                "status": "downloaded",
                "file_path": str(file_path),
                "file_size": len(content),
                "checksum": checksum,
            }

        except Exception as error:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

            # Kiểm tra nếu đã có sẵn file hợp lệ trong output_dir hoặc bronze file_path thì giữ nguyên
            safe_id = safe_filename(document_id)
            existing_files = [
                f for f in self.output_dir.glob(f"{safe_id}.*")
                if f.is_file() and f.suffix.lower() in (".txt", ".html", ".pdf", ".docx") and f.stat().st_size > 200
            ]
            bronze_path = Path(document.get("file_path", "")) if document.get("file_path") else None
            if not existing_files and bronze_path and bronze_path.exists() and bronze_path.stat().st_size > 200:
                dest = self.output_dir / f"{safe_id}{bronze_path.suffix.lower()}"
                shutil.copy2(bronze_path, dest)
                existing_files = [dest]

            if existing_files:
                kept = existing_files[0]
                checksum = self.calculate_checksum(kept)
                self.manifest.update(
                    document_id,
                    status="downloaded_cached",
                    checksum=checksum,
                    file_path=str(kept),
                    source_url=document.get("source_url") or url,
                    file_size=kept.stat().st_size,
                    title=document.get("title", ""),
                    region=document.get("jurisdiction", ""),
                    document_type=document.get("doc_type", ""),
                    language=document.get("language", ""),
                    published_date=document.get("published_date", ""),
                    error=f"Remote fallback ({error}); using local copy {kept.name}",
                )
                return {
                    "document_id": document_id,
                    "status": "downloaded",
                    "file_path": str(kept),
                    "file_size": kept.stat().st_size,
                    "checksum": checksum,
                }

            self.manifest.update(
                document_id,
                status="download_failed",
                source_url=document.get("source_url") or url,
                file_path=None,
                parsed_path=None,
                text_length=None,
                error=str(error),
                parse_error=None,
            )

            return {
                "document_id": document_id,
                "status": "download_failed",
                "error": str(error),
            }

    def collect_from_csv(self, sources_csv: str) -> list:
        """Thu thập danh sách tài liệu từ sources.csv."""
        sources = pd.read_csv(sources_csv, dtype=str, encoding="utf-8-sig").fillna("")

        required_columns = {
            "document_id",
            "title",
            "jurisdiction",
            "doc_type",
            "language",
        }
        missing = required_columns - set(sources.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        sources["document_id"] = sources["document_id"].str.strip()
        if sources["document_id"].duplicated().any():
            raise ValueError("document_id must be unique.")
        if sources["document_id"].eq("").any():
            raise ValueError("document_id cannot be empty.")

        results = []
        for _, row in sources.iterrows():
            document = row.to_dict()
            url = (document.get("download_url") or "").strip() or (document.get("source_url") or "").strip()
            if not url:
                continue
            result = self.collect_one(document)
            results.append(result)
            print(f"{document['document_id']}: {result['status']}")

        total = len(results)
        success = sum(result["status"] == "downloaded" for result in results)
        failed = sum(result["status"] == "download_failed" for result in results)

        print("\n========== COLLECT SUMMARY ==========")
        print(f"Total: {total}")
        print(f"Success: {success}")
        print(f"Failed: {failed}")

        return results
