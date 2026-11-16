"""Capture real localhost pages in a fresh, headless Chrome context."""
from pathlib import Path
import argparse
import base64
import hashlib
import io
import json
import re
import sys
import time
import wave
from datetime import datetime, timezone

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/report_tools'))
from playwright.sync_api import sync_playwright

FIG=ROOT/'docs/bao_cao/hinh_anh'
EVIDENCE=ROOT/'docs/bao_cao/evidence'


def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',action='store_true')
    p.add_argument('--infrastructure-only',action='store_true');p.add_argument('--voice-only',action='store_true')
    p.add_argument('--content-only',action='store_true');args=p.parse_args()
    FIG.mkdir(parents=True,exist_ok=True)
    captures=json.loads((EVIDENCE/'screenshot_manifest.json').read_text(encoding='utf-8')) if (args.infrastructure_only or args.voice_only or args.content_only) and (EVIDENCE/'screenshot_manifest.json').exists() else []
    with sync_playwright() as pw:
        chrome=Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
        browser=pw.chromium.launch(executable_path=str(chrome),headless=True,args=['--disable-gpu'])
        context=browser.new_context(viewport={'width':1600,'height':1050},device_scale_factor=1.5,locale='vi-VN')
        page=context.new_page();page.set_default_timeout(30000)
        page.goto('http://localhost:8501',wait_until='domcontentloaded')
        page.get_by_role('tab',name='Hỏi đáp có dẫn chứng').wait_for()
        page.get_by_text('văn bản đang tra cứu',exact=True).wait_for()
        def capture(filename,caption,locator=None):
            target=FIG/filename
            if locator is None:page.screenshot(path=str(target),full_page=False)
            else:locator.screenshot(path=str(target))
            captures[:]=[c for c in captures if c['file']!='hinh_anh/'+filename]
            captures.append({'file':'hinh_anh/'+filename,'caption':caption,'url':page.url,
                'captured_at':datetime.now(timezone.utc).isoformat(),'kind':'actual browser screenshot'})
            (EVIDENCE/'screenshot_manifest.json').write_text(json.dumps(captures,ensure_ascii=False,indent=2),encoding='utf-8')
            print('Captured',filename,flush=True)
        def infrastructure():
            page.goto('http://localhost:9870/dfshealth.html#tab-overview',wait_until='domcontentloaded')
            page.get_by_text(re.compile('Configured Capacity')).first.wait_for(timeout=45000)
            capture('hinh_3_09_hdfs.png','Giao diện quản trị HDFS NameNode thật, sau khi tải thống kê')
            page.goto('http://localhost:9870/explorer.html#/ai_docs',wait_until='domcontentloaded')
            page.get_by_text('raw',exact=True).first.wait_for()
            capture('hinh_3_10_hdfs_cac_lop.png','Các thư mục dữ liệu trên HDFS')
            page.goto('http://localhost:9870/explorer.html#/ai_docs/processed/20261116_093406_aaf12a03',wait_until='domcontentloaded')
            page.get_by_text(re.compile('part-00000.*snappy.parquet')).first.wait_for()
            capture('hinh_3_30_hdfs_tep_that.png','Tệp Parquet bên trong thư mục: dung lượng thật, replication 1 và block size 128 MiB')
            page.goto('http://localhost:6333/dashboard#/collections',wait_until='domcontentloaded')
            page.get_by_placeholder('Search Collection').fill('ai_documents_verified_v2__api_20261116_093406')
            page.get_by_text('ai_documents_verified_v2__api_20261116_093406_aaf12a03',exact=True).wait_for(timeout=45000)
            capture('hinh_3_11_qdrant.png','Danh sách collection thật trong dashboard Qdrant')
        if args.infrastructure_only:
            infrastructure();browser.close();return
        if args.content_only:
            page.get_by_role('tab',name='Thư viện tài liệu').click()
            page.get_by_text('Danh mục tài liệu',exact=True).scroll_into_view_if_needed()
            page.locator('.document-card').first.wait_for()
            capture('hinh_3_02_thu_vien.png','Thẻ tài liệu và số lượng trong thư viện thật')
            page.get_by_role('tab',name='Tìm văn bản',exact=True).click()
            query=page.get_by_role('textbox',name='Từ khóa hoặc nội dung cần tìm')
            query.fill('Quyết định 102/2026/QĐ-UBND Hà Nội quản lý rủi ro trí tuệ nhân tạo');query.press('Enter')
            page.wait_for_timeout(1600)
            page.get_by_role('button',name='Tìm trong thư viện',exact=True).click()
            source=page.get_by_role('link',name=re.compile('Mở văn bản gốc')).first
            source.wait_for(timeout=45000)
            source.scroll_into_view_if_needed()
            capture('hinh_3_03_tim_kiem.png','Đoạn văn bản tìm được và liên kết đến nguồn chính thức')
            sidebar=page.locator('[data-testid="stSidebar"]')
            sidebar.get_by_text('Tải tài liệu lên',exact=True).click()
            page.locator('input[type="file"]').first.set_input_files(str(ROOT/'data/verified_raw/luat_134_2025.pdf'))
            upload=sidebar.locator('[data-testid="stExpander"]').filter(has_text='Tải tài liệu lên')
            capture('hinh_3_06_chon_tep.png','Tệp PDF được chọn trước khi gửi pipeline',locator=upload)
            browser.close();return
        if args.voice_only:
            page.get_by_role('button',name='Nghe thử giọng đọc',exact=True).scroll_into_view_if_needed()
            page.get_by_role('button',name='Nghe thử giọng đọc',exact=True).click()
            voice_frame=None
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                for frame in page.frames:
                    if frame.locator('#play').count() and not frame.locator('#play').is_disabled():
                        voice_frame=frame;break
                if voice_frame:break
                page.wait_for_timeout(300)
            if voice_frame is None:raise RuntimeError('No prepared presenter frame')
            voice_frame.locator('#play').click()
            voice_frame.locator('#state').filter(has_text='Đang đọc').wait_for(timeout=15000)
            voice_frame.wait_for_function("document.querySelector('#audio').currentTime > .2")
            mouth_samples=[]
            for _ in range(5):
                mouth_samples.append(float(voice_frame.locator('#mouth').get_attribute('ry')))
                page.wait_for_timeout(80)
            state=voice_frame.evaluate('''() => ({provider:CONFIG.provider,segments:CONFIG.segments.length,
                state:document.querySelector('#state').textContent,subtitle:document.querySelector('#subtitle').textContent,
                paused:document.querySelector('#audio').paused,duration:document.querySelector('#audio').duration,
                currentTime:document.querySelector('#audio').currentTime,playbackRate:document.querySelector('#audio').playbackRate})''')
            state['mouth_radius_samples']=mouth_samples
            state['audio_advancing_verified']=state['currentTime']>.2
            state['mouth_animation_verified']=max(mouth_samples)-min(mouth_samples)>.01
            audio_dir=ROOT/'docs/bao_cao/am_thanh';audio_dir.mkdir(exist_ok=True)
            audio_stats=[]
            for i,part in enumerate(voice_frame.evaluate('CONFIG.segments'),1):
                data=base64.b64decode(part['audio_b64']);mime=part.get('mime','audio/mpeg')
                target=audio_dir/(f'nguoi_thuyet_trinh_doan_{i:02d}.'+('wav' if mime=='audio/wav' else 'mp3'))
                target.write_bytes(data)
                stat={'file':'am_thanh/'+target.name,'text':part['text'],'mime':mime,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
                if mime=='audio/wav':
                    with wave.open(io.BytesIO(data)) as wav:
                        stat.update(sample_rate=wav.getframerate(),channels=wav.getnchannels(),sample_width=wav.getsampwidth(),duration_seconds=wav.getnframes()/wav.getframerate())
                audio_stats.append(stat)
            state['audio_files']=audio_stats
            frame_element=voice_frame.frame_element();frame_element.scroll_into_view_if_needed()
            capture('hinh_3_27_nguoi_thuyet_trinh.png','Người thuyết trình nữ, phụ đề và bộ phát khi âm thanh thật đang chạy')
            capture('hinh_3_28_khung_giong_noi.png','Chi tiết khung người nói và điều khiển phát',locator=frame_element)
            voice_frame.locator('#play').click()
            voice_frame.locator('#state').filter(has_text='Tạm dừng').wait_for()
            state['pause_verified']=True
            voice_frame.locator('#speed').select_option('1.15')
            state['speed_verified']=voice_frame.locator('#audio').evaluate('(a)=>a.playbackRate')==1.15
            voice_frame.locator('#restart').click()
            voice_frame.locator('#state').filter(has_text='Đang đọc').wait_for()
            state['restart_verified']=True
            voice_frame.locator('#count').filter(has_text='Đoạn 2 / 2').wait_for(timeout=20000)
            state['subtitle_transition_verified']=True
            voice_frame.locator('#state').filter(has_text='Đã đọc xong').wait_for(timeout=20000)
            state['completion_verified']=True
            (EVIDENCE/'presenter_browser_check.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
            browser.close();return
        capture('hinh_3_01_giao_dien.png','Giao diện chính của ứng dụng đang chạy')
        if args.probe:
            print(json.dumps({'title':page.title(),'buttons':page.get_by_role('button').all_text_contents(),
                'tabs':page.get_by_role('tab').all_text_contents(),'textareas':page.locator('textarea').count(),
                'expanders':page.locator('[data-testid="stExpander"]').all_text_contents()},ensure_ascii=False)[:7000])
            browser.close();return
        page.get_by_role('tab',name='Thư viện tài liệu').click()
        page.get_by_text('Danh mục tài liệu',exact=True).wait_for()
        capture('hinh_3_02_thu_vien.png','Danh mục chỉ hiện văn bản đang tra cứu được')
        page.get_by_role('tab',name='Tìm văn bản',exact=True).click()
        page.get_by_role('textbox',name='Từ khóa hoặc nội dung cần tìm').fill('Quyết định 102/2026/QĐ-UBND Hà Nội quản lý rủi ro trí tuệ nhân tạo')
        page.get_by_role('textbox',name='Từ khóa hoặc nội dung cần tìm').press('Enter')
        page.wait_for_timeout(1600)  # Let Streamlit commit the input rerun before the separate button action.
        page.get_by_role('button',name='Tìm trong thư viện',exact=True).click()
        try:
            page.get_by_role('link',name=re.compile('Mở văn bản gốc')).first.wait_for(timeout=45000)
        except Exception:
            page.screenshot(path=str(EVIDENCE/'capture_search_debug.png'))
            (EVIDENCE/'capture_search_debug.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
            raise
        capture('hinh_3_03_tim_kiem.png','Tìm kiếm văn bản với dẫn chứng và liên kết nguồn thật')
        page.get_by_role('tab',name='Hỏi đáp có dẫn chứng').click()
        page.get_by_role('textbox',name='Câu hỏi của bạn').fill('NIST AI RMF có bốn chức năng quản trị rủi ro cốt lõi nào?')
        page.get_by_role('textbox',name='Câu hỏi của bạn').press('Tab')
        page.wait_for_timeout(1600)
        page.get_by_role('button',name=re.compile('Tra cứu & trả lời')).click()
        page.get_by_text('Nguồn đối chiếu',exact=True).wait_for(timeout=300000)
        page.get_by_text('CÂU HỎI ĐANG ĐỐI CHIẾU',exact=True).scroll_into_view_if_needed()
        capture('hinh_3_04_hoi_dap.png','Câu trả lời LLM có nhãn nguồn trong giao diện thật')
        source=page.locator('[data-testid="stExpander"]').filter(has_text=re.compile(r'\[S\d+\]')).first
        source.locator('summary').click()
        source.scroll_into_view_if_needed()
        capture('hinh_3_05_dan_chung.png','Đoạn nguồn đối chiếu sau câu trả lời')
        sidebar=page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text('Tải tài liệu lên',exact=True).click()
        page.locator('input[type="file"]').first.set_input_files(str(ROOT/'data/verified_raw/luat_134_2025.pdf'))
        sidebar.get_by_text('Tải tài liệu lên',exact=True).scroll_into_view_if_needed()
        capture('hinh_3_06_chon_tep.png','Chọn PDF trước khi gửi xử lý; hình này chưa bấm cập nhật')
        # A fresh tab has no selected upload; the API demonstration must not submit the PDF.
        page.close()
        page=context.new_page();page.set_default_timeout(30000)
        page.goto('http://localhost:8501',wait_until='domcontentloaded')
        page.get_by_role('tab',name='Hỏi đáp có dẫn chứng').wait_for()
        sidebar=page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text('Nguồn cập nhật tự động',exact=True).click()
        sidebar.get_by_role('button',name='Cập nhật dữ liệu',exact=True).scroll_into_view_if_needed()
        sidebar.get_by_role('button',name='Cập nhật dữ liệu',exact=True).click()
        page.locator('[data-testid="stProgress"]').wait_for(timeout=15000)
        capture('hinh_3_07_cap_nhat_api.png','Lượt cập nhật API thật đang chạy nền')
        page.locator('[data-testid="stProgress"]').wait_for(state='detached',timeout=300000)
        sidebar.get_by_role('button',name='Cập nhật dữ liệu',exact=True).scroll_into_view_if_needed()
        capture('hinh_3_08_ket_qua_cap_nhat.png','Kết quả cập nhật và thời điểm kiểm tra nguồn')
        infrastructure()
        browser.close()
    (EVIDENCE/'screenshot_manifest.json').write_text(json.dumps(captures,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
