import fitz  # PyMuPDF
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from src.ingestion.manifest import ManifestManager


class DocumentParser:

    def __init__(
        self,
        raw_dir: str,
        output_dir: str,
        manifest_path: str = "data/manifests/ingestion_manifest.json"
    ):
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.manifest = ManifestManager(manifest_path)

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

    def parse_pdf(self, file_path: Path) -> str:
        """Trích xuất văn bản từ PDF bằng PyMuPDF (fitz) mạnh mẽ."""
        doc = fitz.open(str(file_path))
        pages = []

        for page in doc:
            # Lấy text chuẩn từ trang PDF
            page_text = page.get_text("text") or ""
            if not page_text.strip():
                # Nếu get_text("text") trống, thử trích xuất theo khối (blocks)
                blocks = page.get_text("blocks")
                block_texts = [b[4] for b in blocks if len(b) >= 5 and b[4].strip()]
                page_text = "\n".join(block_texts)

            if page_text.strip():
                pages.append(page_text)

        text = "\n\n".join(pages)

        if not text.strip():
            raise ValueError(
                "PDF không trích xuất được văn bản (file có thể trống hoặc định dạng đặc biệt)."
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

        main_content = soup.find("main") or soup.find("article")
        if main_content is not None:
            text = main_content.get_text(separator="\n")
        else:
            text = soup.get_text(separator="\n")

        text = self.normalize_text(text)
        return text

    def parse_txt(self, file_path: Path) -> str:
        """Đọc nội dung file TXT."""
        raw_bytes = file_path.read_bytes()
        try:
            return raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw_bytes.decode("cp1252", errors="replace")

    def parse_one(self, file_path: Path) -> dict:
        """Phân tích một tài liệu và xuất JSON."""
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
            elif extension == ".txt":
                text = self.parse_txt(file_path)
            else:
                raise ValueError(f"Unsupported file extension: {extension}")

            text = self.normalize_text(text)

            if not text or len(text) < 50:
                raise ValueError(f"Nội dung quá ngắn ({len(text)} ký tự).")

            record = {
                "document_id": document_id,
                "source_file": str(file_path),
                "text": text,
                "text_length": len(text)
            }

            with open(output_path, "w", encoding="utf-8") as file:
                json.dump(record, file, ensure_ascii=False, indent=2)

            self.manifest.update(
                document_id,
                status="parsed",
                parsed_path=str(output_path),
                text_length=len(text),
                parse_error=None
            )

            return {
                "document_id": document_id,
                "status": "parsed",
                "text_length": len(text),
                "output_path": str(output_path)
            }

        except Exception as error:
            if output_path.exists():
                output_path.unlink()

            self.manifest.update(
                document_id,
                status="parse_failed",
                parse_error=str(error)
            )

            return {
                "document_id": document_id,
                "status": "parse_failed",
                "error": str(error)
            }

    def parse_all(self) -> list:
        """Phân tích tất cả tài liệu trong thư mục Raw."""
        results = []
        if not self.raw_dir.exists():
            raise FileNotFoundError(f"Không tìm thấy thư mục Raw: {self.raw_dir}")

        supported_extensions = [".pdf", ".html", ".htm", ".txt"]

        for file_path in sorted(self.raw_dir.iterdir()):
            if not file_path.is_file() or file_path.suffix.lower() not in supported_extensions:
                continue

            result = self.parse_one(file_path)
            results.append(result)
            print(f"{result['document_id']}: {result['status']}")

        total = len(results)
        success = sum(r["status"] == "parsed" for r in results)
        failed = sum(r["status"] == "parse_failed" for r in results)

        print("\n========== PARSE SUMMARY ==========")
        print(f"Total: {total}")
        print(f"Success: {success}")
        print(f"Failed: {failed}")

        return results