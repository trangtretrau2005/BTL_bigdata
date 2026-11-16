"""Incremental official API ingestion. Raw JSON and full text, without PDF downloads."""
from __future__ import annotations
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.catalog import load_inventory, read_json
from src.rag.indexer import _save_json
from src.ingestion.parser import DocumentParser
from src.ingestion.collector import DocumentCollector


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def folded(text):
    text = str(text or '').lower().replace('đ', 'd')
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c)).split())


def ai_related(title, abstract=''):
    return any(term in folded(title + ' ' + abstract) for term in ('tri tue nhan tao', 'artificial intelligence', 'generative ai', 'agentic ai'))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def document_number(title, issued_date=''):
    match = re.search(r'\b\d+/\d{4}/[\wĐđ–-]+', str(title))
    if match:
        return folded(match.group(0)).replace('–', '-')
    # Decisions/directives often omit the year in their number (127/QĐ-TTg).
    match = re.search(r'\b\d+/(?:QĐ|QD|CT|NQ)[–-][\wĐđ–-]+', str(title), re.I)
    year = str(issued_date or '')[:4]
    return folded(match.group(0)).replace('–', '-') + '/' + year if match and year.isdigit() else ''


def plain_text(html):
    if html:
        DocumentCollector.validate_content(html.encode('utf-8'), '.html')
    soup = BeautifulSoup(html or '', 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'iframe']):
        tag.decompose()
    return DocumentParser.normalize_text(soup.get_text('\n', strip=True))


def official_url(url, provider):
    parsed = urlparse(url or '')
    allowed = {'vbpl': {'vbpl.vn', 'vbpl-bientap-gateway.moj.gov.vn'},
               'federal_register': {'www.federalregister.gov', 'www.govinfo.gov'}}
    if parsed.scheme != 'https' or parsed.hostname not in allowed[provider]:
        raise ValueError('API trả về URL ngoài nguồn chính thức đã cấu hình')
    return url


class DynamicIngestor:
    def __init__(self, root=Path('.'), session=None, progress=None):
        self.root = Path(root)
        self.session = session or requests.Session()
        if session is None:
            self.session.headers['User-Agent'] = 'AI-Law-Lake-Academic/3.0 (official public API client)'
            self.session.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=.5,
                status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET', 'POST'])))
        self.config = read_json(self.root / 'data/api_sources.json')
        self.state_path = self.root / 'data/manifests/dynamic_ingestion_manifest.json'
        self.state = read_json(self.state_path)
        self.state.setdefault('documents', {})
        self.state.setdefault('providers', {})
        self.catalog_path = self.root / 'data/dynamic/catalog.json'
        self.catalog = read_json(self.catalog_path)
        rows, _, _ = load_inventory(self.root)
        self.canonical = {}
        self.by_url = {r.get('source_url'): r['document_id'] for r in rows if r.get('source_url')}
        for row in rows:
            number = document_number(row.get('title', ''), row.get('published_date', ''))
            if number:
                self.canonical[(number, folded(row.get('source_org')))] = row['document_id']
        self.progress = progress or (lambda **kwargs: None)

    def _json(self, method, url, **kwargs):
        response = self.session.request(method, url, timeout=(8, 25), **kwargs)
        response.raise_for_status()
        return response.json()

    def _raw(self, provider, group, payload):
        path = self.root / 'data/dynamic/raw' / provider / group / (digest(payload) + '.json')
        if not path.exists():
            _save_json(path, payload)
        return path

    def discover(self, provider, stats):
        cfg = self.config[provider]
        official_url(cfg['catalog_url'], provider)
        checkpoint = self.state['providers'].get(provider, {}).get('last_complete_at')
        initial = datetime.now(timezone.utc) - timedelta(days=int(cfg.get('lookback_days', 730)))
        since = max(initial, datetime.fromisoformat(checkpoint) - timedelta(days=7)) if checkpoint else initial
        cutoff = since.date().isoformat()
        candidates = []
        for page in range(1, int(cfg['max_pages']) + 1):
            try:
                if provider == 'vbpl':
                    payload = self._json('POST', cfg['catalog_url'], json={'pageNumber': page,
                        'pageSize': int(cfg['page_size']), 'keyword': cfg['keyword'],
                        'sortBy': 'issueDate', 'sortDirection': 'DESC'})
                else:
                    payload = self._json('GET', cfg['catalog_url'], params={
                        'conditions[term]': cfg['keyword'], 'conditions[publication_date][gte]': cutoff,
                        'order': 'newest', 'per_page': int(cfg['page_size']), 'page': page})
            except requests.RequestException as exc:
                if not candidates:
                    raise
                stats['discovery_error'] = f'Trang {page}: {exc}'[:400]
                stats['scan_limited'] = True
                break
            if provider == 'vbpl':
                if payload.get('success') is not True:
                    raise ValueError('API Bộ Tư pháp báo không thành công')
                data = payload.get('data') or {}
                items = data.get('items')
                total_pages = max(1, (int(data.get('total', 0)) + int(cfg['page_size']) - 1) // int(cfg['page_size']))
            else:
                items = payload.get('results')
                total_pages = int(payload.get('total_pages') or 1)
            if not isinstance(items, list):
                raise ValueError('API thay đổi cấu trúc danh mục; chưa cập nhật checkpoint')
            self._raw(provider, 'catalog', payload)
            stats['pages'] += 1
            stats['scanned'] += len(items)
            self.progress(provider=provider, message=f"Đang kiểm tra nguồn {cfg['name']} · trang {page}")
            old_page = bool(items)
            for item in items:
                issued = (item.get('issueDate') or item.get('publication_date') or '')[:10]
                if not issued or issued >= cutoff:
                    old_page = False
                if not issued or issued < cutoff or issued > datetime.now(timezone.utc).date().isoformat():
                    continue
                # Do not index a general document just because its full text mentions AI once.
                if not ai_related(item.get('title', ''), item.get('abstract') or item.get('docAbs') or ''):
                    stats['irrelevant'] += 1
                    continue
                candidates.append(item)
            if not items or page >= total_pages or old_page:
                break
            if page == int(cfg['max_pages']):
                stats['scan_limited'] = True
            time.sleep(.1)
        key = 'id' if provider == 'vbpl' else 'document_number'
        unique = {str(item[key]): item for item in candidates}
        return sorted(unique.values(), key=lambda item: item.get('issueDate') or item.get('publication_date') or '', reverse=True)

    def normalize(self, provider, item):
        cfg = self.config[provider]
        remote_id = str(item['id'] if provider == 'vbpl' else item['document_number'])
        if not re.fullmatch(r'[A-Za-z0-9-]+', remote_id):
            raise ValueError('API trả định danh không hợp lệ')
        detail_url = official_url(cfg['detail_url'].format(id=remote_id), provider)
        payload = self._json('GET', detail_url)
        if provider == 'vbpl':
            if payload.get('success') is not True or not isinstance(payload.get('data'), dict):
                raise ValueError('API Bộ Tư pháp chưa có toàn văn hợp lệ')
            data = payload['data']
            if str(data.get('id')) != remote_id or data.get('isTranslationDoc'):
                raise ValueError('Định danh/bản ngôn ngữ của toàn văn không khớp')
            content = (data.get('documentContent') or {}).get('content')
            text = plain_text(content)
            title = data.get('title') or item['title']
            org = data.get('agencyName') or item.get('agencyName') or 'Bộ Tư pháp'
            source = official_url(item.get('document_url') or 'https://vbpl.vn/van-ban/chi-tiet/' + remote_id, provider)
            issued = (data.get('issueDate') or item.get('issueDate') or '')[:10]
            effective = (data.get('effFrom') or item.get('effFrom') or '')[:10]
            status = (data.get('effStatus') or item.get('effStatus') or {}).get('name') or 'unknown'
            kind = (data.get('docType') or item.get('docType') or {}).get('name') or ''
            doc_type = 'policy' if data.get('isAdministrativeDocument') else ('law' if kind == 'Luật' else 'regulation')
            language, region = 'vi', 'VN'
        else:
            data = payload
            if str(data.get('document_number')) != remote_id:
                raise ValueError('Định danh Federal Register không khớp')
            body_url = data.get('body_html_url') or data.get('full_text_xml_url')
            official_url(body_url, provider)
            response = self.session.request('GET', body_url, timeout=(8, 25))
            response.raise_for_status()
            official_url(response.url, provider)
            # Preserve original HTML/XML in the raw JSON envelope, never an abstract as full text.
            payload = {'metadata': data, 'body_url': body_url, 'body': response.text}
            text = plain_text(response.text)
            title = data.get('title') or item['title']
            org = '; '.join(a.get('name', '') for a in data.get('agencies', [])) or 'Federal Register'
            source = official_url(data.get('html_url'), provider)
            issued, effective, status = data.get('publication_date', ''), data.get('effective_on') or '', 'unknown'
            doc_type = 'regulation' if data.get('type') == 'Rule' else 'policy'
            language, region = 'en', 'US'
        if len(text) < 200:
            raise ValueError('Chưa có toàn văn đủ dài; không dùng metadata/tóm tắt thay thế')
        if not ai_related(title, text):
            raise ValueError('Toàn văn không thuộc chủ đề AI')
        number = document_number(title, issued)
        doc_id = self.by_url.get(source) or self.canonical.get((number, folded(org))) or provider + '_' + remote_id
        raw = self._raw(provider, 'documents/' + remote_id, payload)
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        record = {'document_id': doc_id, 'title': title, 'text': text, 'text_length': len(text),
            'source_org': org, 'source_url': source, 'region': region, 'jurisdiction': region,
            'document_type': doc_type, 'language': language, 'published_date': issued,
            'issued_date': issued, 'effective_date': effective or None, 'legal_status': status,
            'status': status, 'version_id': content_hash[:16], 'content_hash': content_hash,
            'parse_status': 'success', 'provenance': 'official_api', 'api_provider': provider,
            'collected_at': utc_now(), 'raw_path': str(raw), 'source_file': str(raw), 'api_url': detail_url}
        row = {'document_id': doc_id, 'title': title, 'source_org': org, 'source_url': source,
            'jurisdiction': region, 'doc_type': doc_type, 'language': language, 'published_date': issued,
            'status': status, 'enabled': 'true', 'origin': 'api', 'api_provider': provider}
        return remote_id, record, row

    def run(self, providers, max_documents=20):
        if not 1 <= max_documents <= 100:
            raise ValueError('Giới hạn cập nhật phải từ 1 đến 100 văn bản mỗi nguồn')
        report = {'providers': {}, 'changed': 0, 'changed_document_ids': [], 'errors': [], 'checked_at': utc_now()}
        for provider_index, provider in enumerate(providers):
            if provider not in self.config or not self.config[provider].get('enabled'):
                raise ValueError('Nguồn API không được bật')
            stats = {'name': self.config[provider]['name'], 'pages': 0, 'scanned': 0,
                     'changed': 0, 'changed_document_ids': [], 'unchanged': 0, 'failed': 0, 'irrelevant': 0, 'backlog': 0, 'scan_limited': False}
            report['providers'][provider] = stats
            try:
                candidates = self.discover(provider, stats)
                if stats.get('discovery_error'):
                    report['errors'].append({'provider': provider, 'error': stats['discovery_error']})
                for candidate_index, item in enumerate(candidates):
                    remote_id = str(item['id'] if provider == 'vbpl' else item['document_number'])
                    key = provider + ':' + remote_id
                    previous = self.state['documents'].get(key, {})
                    fingerprint = digest(item)
                    parsed_path = self.root / 'data/dynamic/parsed' / (previous.get('document_id', '__missing__') + '.json')
                    # Metadata identity excludes retrieval time. A daily full-text check catches unchanged metadata.
                    recent = previous.get('checked_at', '')[:10] == utc_now()[:10]
                    if previous.get('metadata_hash') == fingerprint and parsed_path.is_file() and recent:
                        stats['unchanged'] += 1
                        continue
                    if stats['changed'] >= max_documents:
                        stats['backlog'] += 1
                        continue
                    self.progress(provider=provider, message='Đang lấy toàn văn: ' + item.get('title', remote_id)[:100],
                        progress=5 + 20 * (provider_index + candidate_index / max(1, len(candidates))) / len(providers))
                    try:
                        _, record, row = self.normalize(provider, item)
                        old = read_json(self.root / 'data/dynamic/parsed' / (record['document_id'] + '.json'))
                        changed = any(old.get(k) != record.get(k) for k in ('content_hash', 'title', 'legal_status', 'effective_date', 'source_url'))
                        _save_json(self.root / 'data/dynamic/parsed' / (record['document_id'] + '.json'), record)
                        self.catalog[record['document_id']] = row
                        self.by_url[row['source_url']] = record['document_id']
                        number = document_number(row['title'], row['published_date'])
                        if number:
                            self.canonical[(number, folded(row['source_org']))] = record['document_id']
                        self.state['documents'][key] = {'document_id': record['document_id'], 'metadata_hash': fingerprint,
                            'content_hash': record['content_hash'], 'checked_at': utc_now()}
                        if changed:
                            stats['changed_document_ids'] = sorted(set(stats['changed_document_ids']) | {record['document_id']})
                            report['changed_document_ids'] = sorted(set(report['changed_document_ids']) | {record['document_id']})
                            stats['changed'] = len(stats['changed_document_ids'])
                            report['changed'] = len(report['changed_document_ids'])
                        else:
                            stats['unchanged'] += 1
                        self.progress(provider=provider, message='Đã kiểm tra toàn văn: ' + row['title'][:100])
                    except Exception as exc:
                        stats['failed'] += 1
                        report['errors'].append({'provider': provider, 'document': remote_id, 'error': str(exc)[:400]})
                        self.progress(provider=provider, message='Một nguồn toàn văn chưa sẵn sàng; đang kiểm tra tài liệu tiếp theo.')
                if not stats['failed'] and not stats['backlog'] and not stats['scan_limited']:
                    self.state['providers'][provider] = {'last_complete_at': utc_now()}
                stats['status'] = 'partial' if stats['failed'] or stats['backlog'] or stats['scan_limited'] else 'ok'
            except Exception as exc:
                stats['status'] = 'error'
                report['errors'].append({'provider': provider, 'error': str(exc)[:400]})
            _save_json(self.catalog_path, self.catalog)
            _save_json(self.state_path, self.state)
        _save_json(self.root / 'data/manifests/dynamic_collection_report.json', report)
        if not any(s['status'] != 'error' for s in report['providers'].values()):
            raise RuntimeError('Chưa kết nối được các nguồn API đã chọn. Chỉ mục đang dùng được giữ nguyên.')
        return report
