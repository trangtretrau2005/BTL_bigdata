import csv
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

from bs4 import BeautifulSoup
from src.ingestion.manifest import ManifestManager

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import docx  # python-docx
except ImportError:
    docx = None


SIGNATURE_PATTERN = re.compile(
    r"Người ký:\s*CỔNG THÔNG TIN ĐIỆN TỬ CHÍNH PHỦ.*?(?:Thời gian ký:.*?(\n|$))",
    re.IGNORECASE | re.DOTALL,
)


class DocumentParser:

    def __init__(
        self,
        raw_dir: str,
        output_dir: str,
        manifest_path: str = "data/manifests/ingestion_manifest.json",
        sources_csv: str = "data/sources.csv",
    ):
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = ManifestManager(manifest_path)
        self.catalog_meta: Dict[str, Dict[str, str]] = self._load_catalog_metadata(sources_csv)

    @staticmethod
    def _load_catalog_metadata(sources_csv: str) -> Dict[str, Dict[str, str]]:
        """Đọc metadata từ sources.csv và các file catalog để gắn vào JSON sau khi parse."""
        meta_map: Dict[str, Dict[str, str]] = {}
        csv_paths = [
            Path(sources_csv),
            Path("data/bronze/metadata/vietnam_documents.csv"),
            Path("data/bronze/metadata/international_documents.csv"),
        ]
        for path in csv_paths:
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        doc_id = (row.get("document_id") or "").strip()
                        if not doc_id:
                            continue
                        existing = meta_map.get(doc_id, {})
                        for k, v in row.items():
                            if k and v and str(v).strip():
                                existing[k.strip()] = str(v).strip()
                        meta_map[doc_id] = existing
            except Exception:
                continue
        return meta_map

    def _get_metadata_for(self, document_id: str) -> Dict[str, Any]:
        """Lấy metadata hợp nhất từ catalog CSV và ingestion_manifest.json."""
        csv_meta = self.catalog_meta.get(document_id, {})
        man_meta = self.manifest.get(document_id) or {}

        # Thử tìm không phân biệt hoa thường nếu chưa khớp
        if not csv_meta:
            for k, v in self.catalog_meta.items():
                if k.lower() == document_id.lower() or k.lower().startswith(document_id.lower()):
                    csv_meta = v
                    break

        title = (
            csv_meta.get("title")
            or man_meta.get("title")
            or document_id
        )
        source_url = (
            csv_meta.get("source_url")
            or man_meta.get("source_url")
            or csv_meta.get("download_url")
            or ""
        )
        region = (
            csv_meta.get("jurisdiction")
            or csv_meta.get("region")
            or man_meta.get("region")
            or "UNKNOWN"
        )
        document_type = (
            csv_meta.get("doc_type")
            or csv_meta.get("document_type")
            or man_meta.get("document_type")
            or "policy"
        )
        language = (
            csv_meta.get("language")
            or man_meta.get("language")
            or "vi"
        )
        published_date = (
            csv_meta.get("published_date")
            or csv_meta.get("version_date")
            or man_meta.get("published_date")
            or ""
        )
        status = csv_meta.get("status") or "current"

        return {
            "title": title,
            "source_url": source_url,
            "region": region,
            "jurisdiction": region,
            "document_type": document_type,
            "language": language,
            "published_date": published_date,
            "status": status,
        }

    @staticmethod
    def repair_mojibake(text: str) -> str:
        """Thử sửa lỗi UTF-8 bị giải mã nhầm."""
        markers = ("Ã", "Â", "Ä", "á»", "áº", "â€™", "â€œ", "â€")
        old_score = sum(text.count(marker) for marker in markers)
        if old_score == 0:
            return text

        for encoding in ("cp1252", "latin1"):
            try:
                repaired = text.encode(encoding).decode("utf-8")
                new_score = sum(repaired.count(marker) for marker in markers)
                if new_score < old_score:
                    return repaired
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        return text

    @staticmethod
    def normalize_text(text: str) -> str:
        """Chuẩn hóa văn bản trước khi lưu."""
        text = text.replace("\x00", " ")
        text = DocumentParser.repair_mojibake(text)
        text = re.sub(r"\r\n?", "\n", text)
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def is_only_digital_signature(text: str) -> bool:
        """Kiểm tra xem văn bản trích xuất có phải chỉ là con dấu chữ ký số của PDF scan không."""
        cleaned = SIGNATURE_PATTERN.sub("", text).strip()
        if len(cleaned) < 200 and (
            "cổng thông tin điện tử chính phủ" in text.lower()
            or "thời gian ký:" in text.lower()
            or "người ký:" in text.lower()
        ):
            return True
        return False

    def parse_pdf(self, file_path: Path) -> str:
        """Trích xuất văn bản từ PDF bằng PyMuPDF (fitz)."""
        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) chưa được cài đặt.")

        doc = fitz.open(str(file_path))
        pages = []

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text") or ""
            if not page_text.strip():
                blocks = page.get_text("blocks")
                block_texts = [b[4] for b in blocks if len(b) >= 5 and isinstance(b[4], str) and b[4].strip()]
                page_text = "\n".join(block_texts)

            if page_text.strip():
                pages.append(f"[Trang {page_num}]\n{page_text.strip()}")

        text = "\n\n".join(pages)

        if not text.strip():
            raise ValueError(
                "PDF không trích xuất được văn bản (file scan ảnh hoặc trống)."
            )

        if self.is_only_digital_signature(text):
            raise ValueError(
                "PDF là bản scan ảnh (chỉ trích xuất được chữ ký số 148 ký tự, không có nội dung văn bản luật)."
            )

        return text

    def parse_html(self, file_path: Path) -> str:
        """Trích xuất nội dung chính từ HTML."""
        html_bytes = file_path.read_bytes()
        html_lower = html_bytes[:20000].lower()

        blocked_markers = [
            b"awswafintegration", b"gokuprops", b"challenge-container",
            b"token.awswaf.com", b"captcha", b"challenge.js"
        ]

        for marker in blocked_markers:
            if marker in html_lower:
                raise ValueError("HTML là trang xác minh/chặn truy cập.")

        soup = BeautifulSoup(html_bytes, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"]):
            tag.decompose()

        for tag in soup.select('[role="navigation"], [role="banner"], [role="contentinfo"], form'):
            tag.decompose()

        main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|toanvan|article|body", re.I))
        if main_content is not None:
            text = main_content.get_text(separator="\n")
        else:
            text = soup.get_text(separator="\n")

        text = self.normalize_text(text)
        return text

    def parse_docx(self, file_path: Path) -> str:
        """Trích xuất văn bản và bảng từ file DOCX (FR03)."""
        if docx is None:
            raise RuntimeError("Thư viện python-docx chưa được cài đặt.")
        document = docx.Document(str(file_path))
        parts = []
        for para in document.paragraphs:
            if para.text.strip():
                parts.append(para.text.strip())
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts)

    def parse_txt(self, file_path: Path) -> str:
        """Đọc nội dung file TXT."""
        raw_bytes = file_path.read_bytes()
        try:
            return raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw_bytes.decode("cp1252", errors="replace")

    def parse_one(self, file_path: Path) -> dict:
        """Phân tích một tài liệu và xuất JSON đầy đủ metadata."""
        document_id = file_path.stem
        output_path = self.output_dir / f"{document_id}.json"

        try:
            if not file_path.exists():
                raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

            if file_path.stat().st_size == 0:
                raise ValueError("File rỗng.")

            extension = file_path.suffix.lower()

            if extension == ".pdf":
                text = self.parse_pdf(file_path)
            elif extension in [".html", ".htm"]:
                text = self.parse_html(file_path)
            elif extension == ".docx":
                text = self.parse_docx(file_path)
            elif extension == ".txt":
                text = self.parse_txt(file_path)
            else:
                raise ValueError(f"Unsupported file extension: {extension}")

            text = self.normalize_text(text)

            if not text or len(text) < 200:
                raise ValueError(f"Nội dung quá ngắn ({len(text)} ký tự, yêu cầu >= 200 ký tự).")

            meta = self._get_metadata_for(document_id)

            record = {
                "document_id": document_id,
                "title": meta["title"],
                "source_url": meta["source_url"],
                "region": meta["region"],
                "jurisdiction": meta["jurisdiction"],
                "document_type": meta["document_type"],
                "language": meta["language"],
                "published_date": meta["published_date"],
                "status": meta["status"],
                "source_file": str(file_path),
                "text": text,
                "text_length": len(text),
            }

            with open(output_path, "w", encoding="utf-8") as file:
                json.dump(record, file, ensure_ascii=False, indent=2)

            self.manifest.update(
                document_id,
                status="parsed",
                parsed_path=str(output_path),
                text_length=len(text),
                title=meta["title"],
                region=meta["region"],
                document_type=meta["document_type"],
                language=meta["language"],
                parse_error=None,
            )

            return {
                "document_id": document_id,
                "status": "parsed",
                "text_length": len(text),
                "output_path": str(output_path),
            }

        except Exception as error:
            self.manifest.update(
                document_id,
                status="parse_failed",
                parse_error=str(error),
            )

            return {
                "document_id": document_id,
                "status": "parse_failed",
                "error": str(error),
            }

    def parse_all(self) -> list:
        """Phân tích tất cả tài liệu trong thư mục Raw."""
        results = []
        if not self.raw_dir.exists():
            raise FileNotFoundError(f"Không tìm thấy thư mục Raw: {self.raw_dir}")

        supported_extensions = [".pdf", ".html", ".htm", ".docx", ".txt"]

        # Ưu tiên .txt / .html / .docx nếu cùng document_id có bản PDF bị lỗi scan
        files_by_stem: Dict[str, list[Path]] = {}
        for file_path in sorted(self.raw_dir.iterdir()):
            if not file_path.is_file() or file_path.suffix.lower() not in supported_extensions:
                continue
            files_by_stem.setdefault(file_path.stem, []).append(file_path)

        priority = {".txt": 1, ".html": 2, ".htm": 2, ".docx": 3, ".pdf": 4}

        for stem, fpaths in sorted(files_by_stem.items()):
            fpaths_sorted = sorted(fpaths, key=lambda p: priority.get(p.suffix.lower(), 99))
            last_result = None
            for fp in fpaths_sorted:
                res = self.parse_one(fp)
                last_result = res
                if res["status"] == "parsed":
                    break
            if last_result:
                results.append(last_result)
                print(f"{last_result['document_id']}: {last_result['status']}")

        total = len(results)
        success = sum(r["status"] == "parsed" for r in results)
        failed = sum(r["status"] == "parse_failed" for r in results)

        print("\n========== PARSE SUMMARY ==========")
        print(f"Total: {total}")
        print(f"Success: {success}")
        print(f"Failed: {failed}")

        return results
