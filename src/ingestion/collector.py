import hashlib
import re
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
        manifest_path: str
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

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
            "Connection": "keep-alive"
        })

        # Cấu hình Retry
        retry_strategy = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1,
            status_forcelist=[
                429,
                500,
                502,
                503,
                504
            ],
            allowed_methods=frozenset(["GET"]),
            respect_retry_after_header=True
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy
        )

        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    @staticmethod
    def calculate_checksum(file_path: Path) -> str:
        """Tính mã SHA256 của file."""
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as file:
            for chunk in iter(
                lambda: file.read(1024 * 1024),
                b""
            ):
                sha256.update(chunk)

        return sha256.hexdigest()

    @staticmethod
    def detect_extension(
        url: str,
        content_type: str,
        content: bytes
    ) -> str:
        """Xác định định dạng dựa trên nội dung thực tế."""
        url_path = urlparse(url).path.lower()
        content_start = content[:1000].lstrip().lower()

        # Nhận diện PDF bằng chữ ký file
        if content.startswith(b"%PDF-"):
            return ".pdf"

        # Nhận diện HTML
        is_html = (
            "text/html" in content_type
            or "application/xhtml+xml" in content_type
            or content_start.startswith(b"<!doctype html")
            or content_start.startswith(b"<html")
            or b"<html" in content_start
        )

        if is_html:
            return ".html"

        # Nhận diện TXT
        if (
            url_path.endswith(".txt")
            or "text/plain" in content_type
        ):
            return ".txt"

        raise ValueError(
            "Không nhận diện được định dạng tài liệu. "
            f"Content-Type: {content_type}"
        )

    @staticmethod
    def validate_content(
        content: bytes,
        extension: str
    ) -> None:
        """
        Kiểm tra nội dung thực tế trước khi lưu.
        Từ chối trang chống bot, trang chuyển hướng
        và nội dung không đủ điều kiện.
        """
        if not content or not content.strip():
            raise ValueError(
                "Response rỗng."
            )

        # Kiểm tra PDF
        if extension == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise ValueError(
                    "File không có chữ ký PDF hợp lệ."
                )
            return

        # Kiểm tra HTML
        if extension == ".html":
            html_lower = content[:50000].lower()

            blocked_markers = [
                b"awswaf",
                b"awswafintegration",
                b"challenge.js",
                b"challenge-container",
                b"gokuprops",
                b"captcha",
                b"token.awswaf.com",
                b"request blocked",
                b"robot check"
            ]

            for marker in blocked_markers:
                if marker in html_lower:
                    raise ValueError(
                        "Nguồn trả về trang chống bot/"
                        "xác minh truy cập. "
                        f"Phát hiện: {marker.decode('utf-8', errors='replace')}"
                    )

            soup = BeautifulSoup(
                content,
                "html.parser"
            )

            # Loại bỏ thành phần không phải nội dung chính
            for tag in soup([
                "script",
                "style",
                "noscript",
                "svg",
                "iframe"
            ]):
                tag.decompose()

            text = soup.get_text(
                separator=" ",
                strip=True
            )

            # Kiểm tra trang chuyển hướng
            redirect_messages = [
                "you are being redirected",
                "redirecting you",
                "please wait while you are redirected",
                "please wait while we redirect",
                "redirecting..."
            ]

            if any(
                message in text.lower()
                for message in redirect_messages
            ):
                raise ValueError(
                    "Nguồn chỉ trả về trang chuyển hướng, "
                    "không phải nội dung tài liệu."
                )

            # Kiểm tra độ dài nội dung
            if len(text) < 100:
                raise ValueError(
                    f"Nội dung HTML quá ngắn ({len(text)} ký tự)."
                )

        # Kiểm tra TXT
        elif extension == ".txt":
            if len(content.strip()) < 100:
                raise ValueError(
                    "Nội dung TXT quá ngắn."
                )

    def download_content(self, url: str):
        """Tải nội dung từ URL bằng HTTP Session."""
        response = self.session.get(
            url,
            timeout=(10, 60),
            allow_redirects=True
        )

        response.raise_for_status()
        content = response.content

        if not content:
            raise ValueError(
                "Server trả về response rỗng."
            )

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        return (
            content,
            content_type,
            response.url
        )

    def collect_one(self, document: dict) -> dict:
        """Thu thập một tài liệu và cập nhật Manifest."""
        document_id = document["document_id"]
        url = document["download_url"]

        file_path = None
        temp_path = None

        try:
            # Bước 1: Tải nội dung
            content, content_type, final_url = (
                self.download_content(url)
            )

            # Bước 2: Nhận diện định dạng
            extension = self.detect_extension(
                final_url,
                content_type,
                content
            )

            # Bước 3: Kiểm tra chất lượng nội dung
            self.validate_content(
                content,
                extension
            )

            # Bước 4: Tạo tên và đường dẫn file
            filename = safe_filename(
                document_id + extension
            )

            file_path = self.output_dir / filename
            temp_path = file_path.with_name(
                file_path.name + ".tmp"
            )

            # Bước 5: Ghi file tạm trước
            try:
                with open(temp_path, "wb") as file:
                    file.write(content)

                if (
                    not temp_path.exists()
                    or temp_path.stat().st_size == 0
                ):
                    raise ValueError(
                        "File tải xuống bị rỗng."
                    )

                # Chỉ chuyển thành file chính thức sau khi ghi thành công
                temp_path.replace(file_path)

            finally:
                if temp_path.exists():
                    temp_path.unlink()

            # Bước 6: Tính checksum
            checksum = self.calculate_checksum(file_path)

            # Bước 7: Cập nhật Manifest (map các cột mới sang chuẩn manifest cũ)
            self.manifest.update(
                document_id,
                status="downloaded",
                checksum=checksum,
                file_path=str(file_path),
                source_url=url,
                final_url=final_url,
                content_type=content_type,
                file_size=len(content),
                title=document["title"],
                region=document.get("jurisdiction", ""),
                document_type=document.get("doc_type", ""),
                language=document["language"],
                error=None,
                parse_error=None,
                parsed_path=None,
                text_length=None
            )

            return {
                "document_id": document_id,
                "status": "downloaded",
                "file_path": str(file_path),
                "file_size": len(content),
                "checksum": checksum
            }

        except Exception as error:
            # Xóa file tạm nếu có
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

            # Xóa file Raw cũ cùng document_id
            safe_id = safe_filename(document_id)
            for old_file in self.output_dir.glob(
                f"{safe_id}.*"
            ):
                if old_file.is_file():
                    old_file.unlink()

            # Cập nhật trạng thái thất bại
            self.manifest.update(
                document_id,
                status="download_failed",
                source_url=url,
                file_path=None,
                parsed_path=None,
                text_length=None,
                error=str(error),
                parse_error=None
            )

            return {
                "document_id": document_id,
                "status": "download_failed",
                "error": str(error)
            }

    def collect_from_csv(self, sources_csv: str) -> list:
        """Thu thập danh sách tài liệu từ sources.csv."""
        sources = pd.read_csv(
            sources_csv,
            dtype=str,
            encoding="utf-8-sig"
        ).fillna("")

        # Các cột bắt buộc theo cấu trúc CSV mới
        required_columns = {
            "document_id",
            "title",
            "jurisdiction",
            "doc_type",
            "download_url",
            "language"
        }

        missing = required_columns - set(sources.columns)

        if missing:
            raise ValueError(
                f"Missing columns: {missing}"
            )

        # Kiểm tra document_id trùng lặp
        sources["document_id"] = (
            sources["document_id"].str.strip()
        )

        if sources["document_id"].duplicated().any():
            raise ValueError(
                "document_id must be unique."
            )

        # Kiểm tra trường bắt buộc không được rỗng
        # Kiểm tra document_id không được rỗng
        if sources["document_id"].eq("").any():
            raise ValueError(
                "document_id cannot be empty."
            )

        # Chỉ lọc ra các dòng có download_url hợp lệ để tiến hành tải
        sources = sources[sources["download_url"].str.strip() != ""]

        # Kiểm tra URL
        for url in sources["download_url"]:
            parsed_url = urlparse(url.strip())

            if (
                parsed_url.scheme not in ["http", "https"]
                or not parsed_url.netloc
            ):
                raise ValueError(
                    f"Invalid source URL: {url}"
                )

        results = []

        # Thu thập từng tài liệu
        for _, row in sources.iterrows():
            document = row.to_dict()

            result = self.collect_one(document)

            results.append(result)

            print(
                f"{document['document_id']}: "
                f"{result['status']}"
            )

        # Tổng hợp kết quả
        total = len(results)

        success = sum(
            result["status"] == "downloaded"
            for result in results
        )

        failed = sum(
            result["status"] == "download_failed"
            for result in results
        )

        print("\n========== COLLECT SUMMARY ==========")
        print(f"Total: {total}")
        print(f"Success: {success}")
        print(f"Failed: {failed}")

        return results