"""Visual QA for generated report HTML, in a fresh local Chrome session."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/report_tools'))
from playwright.sync_api import sync_playwright


def main():
    out=ROOT/'docs/bao_cao';e=out/'evidence';checks=[]
    with sync_playwright() as pw:
        b=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=b.new_page(viewport={'width':1400,'height':1100},device_scale_factor=1)
        for filename,expected in [('02_BAN_NHAP_CHUONG_2_3.html',40),('03_BIEU_DO_THONG_KE.html',16)]:
            page.goto((out/filename).as_uri(),wait_until='load')
            page.wait_for_function('Array.from(document.images).every(i=>i.complete)')
            result=page.evaluate('''() => ({images:document.images.length,
                brokenImages:Array.from(document.images).filter(i=>!i.naturalWidth).map(i=>i.src),
                viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
                font:getComputedStyle(document.body).fontFamily,
                tables:document.querySelectorAll('table').length,
                headings:document.querySelectorAll('h1,h2,h3').length})''')
            assert result['images']==expected and not result['brokenImages'],result
            assert result['documentWidth']<=result['viewport'],result
            page.screenshot(path=str(e/(Path(filename).stem+'_preview.png')))
            result['file']=filename;checks.append(result)
        page.goto((out/'02_BAN_NHAP_CHUONG_2_3.html').as_uri(),wait_until='load')
        for term,filename in [('2.3. Kiến trúc và flowchart toàn hệ thống','report_design_preview.png'),
            ('3.10. Thử nghiệm trợ lý giọng nói và người thuyết trình','report_presenter_preview.png')]:
            page.get_by_role('heading',name=term,exact=True).scroll_into_view_if_needed()
            page.screenshot(path=str(e/filename))
        b.close()
    (e/'html_visual_check.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print('HTML visual check passed: all images loaded; no horizontal overflow.')


if __name__=='__main__':main()
