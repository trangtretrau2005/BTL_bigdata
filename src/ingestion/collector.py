"""Collect original documents with explicit provenance; never manufacture legal text."""
from __future__ import annotations

import csv
import hashlib
import os
import io
import zipfile
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.ingestion.manifest import ManifestManager


def safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '_', name).strip(' .')
    if not name or name in {'.', '..'}:
        raise ValueError('document_id không hợp lệ')
    return name


class DocumentCollector:
    def __init__(self, output_dir: str, manifest_path: str = 'data/manifests/ingestion_manifest.json', *, timeout: int = 30):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = ManifestManager(manifest_path)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'AI-Law-Research-Corpus/2.0 (academic document retrieval)', 'Accept': 'application/pdf,text/html,application/xhtml+xml;q=0.9,*/*;q=0.5'})
        retry = Retry(total=1, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'])
        self.session.mount('https://', HTTPAdapter(max_retries=retry))

    @staticmethod
    def calculate_checksum(file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def detect_extension(url: str, content_type: str, content: bytes) -> str:
        start = content[:2000].lstrip().lower()
        if content.startswith(b'%PDF-'):
            return '.pdf'
        if content.startswith(b'PK\x03\x04'):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if 'word/document.xml' in archive.namelist():
                    return '.docx'
        if 'html' in content_type or b'<html' in start or b'<!doctype html' in start:
            return '.html'
        if 'xml' in content_type or start.startswith(b'<?xml'):
            return '.xml'
        if 'text/plain' in content_type or urlparse(url).path.lower().endswith('.txt'):
            return '.txt'
        raise ValueError(f'Không nhận diện được định dạng gốc: {content_type}')

    @staticmethod
    def validate_content(content: bytes, extension: str) -> None:
        if not content or len(content.strip()) < 100:
            raise ValueError('Tài liệu rỗng hoặc quá ngắn')
        if extension == '.pdf' and not content.startswith(b'%PDF-'):
            raise ValueError('Thiếu chữ ký PDF')
        if extension == '.html':
            soup = BeautifulSoup(content, 'html.parser')
            for tag in soup(['script', 'style', 'noscript', 'nav', 'footer']):
                tag.decompose()
            visible = soup.get_text(' ', strip=True)
            title = soup.title.get_text(' ', strip=True).lower() if soup.title else ''
            blocked = ('just a moment', 'access denied', 'request access', 'request blocked', 'robot check', 'page not found', '404 not found')
            if any(word in title for word in blocked) or len(visible) < 200:
                raise ValueError('Trang lỗi/chặn truy cập, không phải toàn văn')
            if len(visible) < 3000 and any(word in visible.lower() for word in ('verify you are human', 'enable javascript and cookies', 'you are being redirected')):
                raise ValueError('Trang xác minh/chuyển hướng, không phải toàn văn')

    def _get(self, url: str):
        response = self.session.get(url, timeout=(10, self.timeout), allow_redirects=True)
        response.raise_for_status()
        return response

    def fetch_via_official_api(self, url: str):
        match = re.search(r'federalregister\.gov/documents/\d{4}/\d{2}/\d{2}/([\d-]+)', url)
        if match:
            metadata = self._get(f'https://www.federalregister.gov/api/v1/documents/{match.group(1)}.json').json()
            full_text = metadata.get('body_html_url') or metadata.get('full_text_xml_url')
            if not full_text:
                raise ValueError('Federal Register API không cung cấp URL toàn văn')
            body = self._get(full_text)
            return body.content, body.headers.get('Content-Type', 'text/html'), body.url
        return None

    def download_content(self, url: str):
        if urlparse(url).scheme not in {'http', 'https'}:
            raise ValueError('Nguồn phải là URL HTTP(S) công khai')
        api_result = self.fetch_via_official_api(url)
        if api_result:
            return api_result
        response = self._get(url)
        # Công báo publishes original PDF/DOCX via a public download API.
        # Resolve its links from the official page; never index the landing page as a law.
        if urlparse(url).hostname == 'congbao.chinhphu.vn' and not response.content.startswith(b'%PDF-'):
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            for tag in soup.select('a[href], [data-href]'):
                link = urljoin(response.url, tag.get('data-href') or tag.get('href') or '')
                host = urlparse(link).hostname or ''
                if host.endswith('cdnchinhphu.vn') or host == 'congbaocdn.chinhphu.vn':
                    if any(ext in unquote(link).lower() for ext in ('.docx', '.pdf')):
                        links.append(link)
            links = sorted(set(links), key=lambda link: ('.docx' not in unquote(link).lower(), link))
            for link in links:
                try:
                    asset = self._get(link)
                    if asset.content.startswith((b'%PDF-', b'PK\x03\x04')):
                        return asset.content, asset.headers.get('Content-Type', '').lower(), asset.url
                except requests.RequestException:
                    continue
            raise ValueError('Không tìm được tệp toàn văn từ API Công báo')
        return response.content, response.headers.get('Content-Type', '').lower(), response.url

    def collect_one(self, document: dict, *, refresh: bool = False) -> dict:
        document_id = safe_filename(document['document_id'])
        previous = self.manifest.get(document_id) or {}
        existing = Path(str(previous.get('file_path') or self.output_dir / '__missing__').replace('\\', '/'))
        if not refresh and previous.get('provenance') == 'official_download' and existing.is_file():
            if self.calculate_checksum(existing) == previous.get('checksum'):
                return {'document_id': document_id, 'status': 'downloaded_cached', 'file_path': str(existing)}
        urls = list(dict.fromkeys(u.strip() for u in [document.get('download_url', ''), *document.get('alternate_urls', '').split('|'), document.get('source_url', '')] if u.strip()))
        errors = []
        for url in urls:
            try:
                content, content_type, final_url = self.download_content(url)
                extension = self.detect_extension(final_url, content_type, content)
                self.validate_content(content, extension)
                if document.get('file_format') == 'pdf' and extension != '.pdf':
                    raise ValueError('Nguồn PDF trả về trang web/metadata, không phải PDF toàn văn')
                target = self.output_dir / f'{document_id}{extension}'
                temporary = target.with_name(target.name + '.tmp')
                temporary.write_bytes(content)
                temporary.replace(target)
                checksum = self.calculate_checksum(target)
                metadata = {key: document.get(key, '') for key in ('title', 'source_org', 'source_url', 'language', 'published_date', 'effective_date', 'version_id')}
                self.manifest.update(document_id, **metadata, status='downloaded', legal_status=document.get('status') or 'unknown', region=document.get('jurisdiction', ''), document_type=document.get('doc_type', ''), checksum=checksum, file_path=str(target), final_url=final_url, download_url=url, content_type=content_type, file_size=len(content), provenance='official_download', collected_at=datetime.now(timezone.utc).isoformat(), error=None, parse_error=None)
                return {'document_id': document_id, 'status': 'downloaded', 'file_path': str(target), 'file_size': len(content), 'checksum': checksum}
            except Exception as exc:
                errors.append(f'{url}: {type(exc).__name__}: {exc}')
        self.manifest.update(document_id, title=document.get('title', ''), source_url=document.get('source_url', ''), status='download_failed', error='; '.join(errors), provenance='download_failed')
        return {'document_id': document_id, 'status': 'download_failed', 'error': '; '.join(errors)}

    def collect_from_csv(self, sources_csv: str, *, refresh: bool = False, limit: int | None = None) -> list:
        with open(sources_csv, encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            required = {'document_id', 'title', 'source_url', 'jurisdiction', 'doc_type', 'language'}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f'Thiếu cột: {required - set(reader.fieldnames or [])}')
            documents = [{k: (v or '').strip() for k, v in row.items() if k} for row in reader]
        documents = [d for d in documents if d.get('document_id') and d.get('enabled', 'true').lower() != 'false']
        ids = [d['document_id'] for d in documents]
        if len(ids) != len(set(ids)):
            raise ValueError('document_id phải duy nhất')
        results = []
        for document in documents[:limit]:
            result = self.collect_one(document, refresh=refresh)
            results.append(result)
            print(f"{document['document_id']}: {result['status']}", flush=True)
            time.sleep(float(os.getenv('COLLECTION_DELAY', '0.15')))
        print(f"Collected: {sum(r['status'] in ('downloaded', 'downloaded_cached') for r in results)}/{len(results)}", flush=True)
        return results
