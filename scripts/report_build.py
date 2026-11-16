"""Build the report bundle and validate all local links and image assets."""
from pathlib import Path
import csv
import hashlib
import html
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/report_tools'))
import markdown
from PIL import Image, ImageDraw, ImageFont

OUT=ROOT/'docs/bao_cao'
E=OUT/'evidence'
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')

STYLE='''
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:#233644;background:#eeeae1;font:18px/1.65 "Times New Roman",serif}
main{max-width:1150px;margin:35px auto;padding:55px 65px;background:#fffefb;border-top:7px solid #173e59;box-shadow:0 8px 36px #173e5915}
h1,h2,h3{color:#173e59;line-height:1.3;break-after:avoid}h1{font-size:29px;margin-top:2.4em;padding-bottom:12px;border-bottom:2px solid #c49232}h1:first-child{margin-top:0}h2{font-size:24px;margin-top:2em}h3{font-size:21px;margin-top:1.5em}
p{text-align:justify}a{color:#225d7c;text-decoration-thickness:1px;text-underline-offset:3px}img{display:block;max-width:100%;height:auto;margin:25px auto 10px;border:1px solid #eee;cursor:zoom-in}p:has(img){text-align:center}
p:has(img)+p{color:#59656e;font-size:16px}table{width:100%;border-collapse:collapse;font-size:16px;line-height:1.45;margin:24px 0;overflow-wrap:anywhere}th{background:#173e59;color:white;text-align:left}td,th{padding:10px 12px;border:1px solid #d9e0e3;vertical-align:top}tr:nth-child(even){background:#f2f5f5}
code{font:14px/1.5 Consolas,monospace;background:#edf1f2;overflow-wrap:anywhere}pre{padding:18px;background:#edf1f2;overflow:auto;white-space:pre-wrap}blockquote{border-left:4px solid #c49232;margin-left:0;padding-left:20px;color:#4a5d69}.toc{background:#f2f5f5;padding:18px 28px;border-radius:8px;font-size:16px}.toc li{margin:3px 0}.toc ul{padding-left:23px}footer{color:#647581;font-size:14px;margin-top:40px;border-top:1px solid #d9e0e3;padding-top:14px}
@media(max-width:800px){main{margin:0;padding:25px 20px}body{font-size:17px}table{font-size:14px}}
@page{size:A4;margin:20mm 18mm} @media print{body{background:white;font-size:12pt;line-height:1.5}main{padding:0;margin:0;max-width:none;border:0;box-shadow:none}h1{break-before:page;font-size:18pt}h1:first-child{break-before:auto}h2{font-size:15pt}h3{font-size:13pt}table{font-size:9pt}thead{display:table-header-group}tr{break-inside:avoid}img{max-height:235mm;object-fit:contain}a{color:inherit;text-decoration:none}.toc{break-after:page}footer{font-size:9pt}}
'''


def render(source,target,title):
    body=markdown.markdown('[TOC]\n\n'+source,extensions=['tables','fenced_code','toc','sane_lists'],
        extension_configs={'toc':{'toc_depth':'1-2','title':'Mục lục nội dung'}})
    document=f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main>{body}<footer>Bản nháp từ mã nguồn và phép đo ngày 16/11/2026. Hình sơ đồ/biểu đồ có bản SVG; ảnh ứng dụng là ảnh chụp thật.</footer></main><script>document.querySelectorAll("img").forEach(i=>i.addEventListener("click",()=>window.open(i.src,"_blank","noopener")))</script></body></html>'
    (OUT/target).write_text(document,encoding='utf-8')


def cell(value):
    return str(value or '').replace('|','/').replace('\n',' ').replace('\r',' ')


def main():
    facts=json.loads((E/'system_facts.json').read_text(encoding='utf-8'))
    docs=list(csv.DictReader((E/'document_statistics.csv').open(encoding='utf-8-sig')))
    active=json.loads((E/'active_documents.json').read_text(encoding='utf-8'))
    source={d['document_id']:d for d in active}
    catalog=[]
    for d in sorted(docs,key=lambda d:(d['region'],d['title'])):
        s=source[d['source_document_id']]
        catalog.append({**d,'source_org':s.get('source_org',''),'source_url':s.get('source_url','')})
    with (E/'dataset_catalog.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(catalog[0]));w.writeheader();w.writerows(catalog)
    appendix=['# PHỤ LỤC. DANH MỤC DỮ LIỆU ĐANG HOẠT ĐỘNG',
        '\nSnapshot: `'+facts['index']['snapshot']+'`. Có 63 tài liệu; thống kê lấy từ Processed và catalog cùng phiên bản, ngày 16/11/2026. URL là địa chỉ nguồn của bản đã thu thập, không xác nhận lại hiệu lực pháp lý. Nhãn INTERNATIONAL là nhóm gộp theo schema hiện tại.',
        '\n[CSV đầy đủ, gồm ngày và trạng thái](evidence/dataset_catalog.csv). [Về báo cáo](02_BAN_NHAP_CHUONG_2_3.md).',
        '\n| STT | ID nguồn / tài liệu | Cơ quan | Khu vực / ngôn ngữ | Loại / provenance | Ký tự / đoạn | Nguồn |',
        '|---|---|---|---|---|---:|---|']
    for i,d in enumerate(catalog,1):
        appendix.append('| '+ ' | '.join([str(i),cell(d['title'])+'<br>`'+cell(d['source_document_id'])+'`',cell(d['source_org']),cell(d['region'])+' / '+cell(d['language']),cell(d['document_type'])+' / '+cell(d['provenance']),f"{int(d['characters']):,} / {d['chunks']}",f"[Nguồn]({d['source_url']})" if d['source_url'] else 'Tệp nội bộ'])+' |')
    queries=list(csv.DictReader((E/'retrieval_cases.csv').open(encoding='utf-8-sig')))
    appendix+=['\n## Bộ truy vấn đánh giá','\n15 câu độc lập, mỗi câu lặp ba lượt; bộ lọc khu vực được công khai, không lọc document_id.','\n| Mã | Câu hỏi | ID tài liệu kỳ vọng | Lọc khu vực |','|---|---|---|---|']
    for q in queries:appendix.append('| '+' | '.join(cell(q[k]) for k in ['case_id','question','expected_document_id','region_filter'])+' |')
    (OUT/'PHU_LUC_DANH_MUC_DU_LIEU.md').write_text('\n'.join(appendix)+'\n',encoding='utf-8')
    intro='''# BẢN NHÁP BÁO CÁO — CHƯƠNG 2 VÀ CHƯƠNG 3

**Đề tài:** Xây dựng nền tảng Data Lake tích hợp RAG và LLM hỗ trợ tra cứu, hỏi đáp văn bản pháp luật, chính sách và quy định về trí tuệ nhân tạo.

**Học phần:** Dữ liệu lớn — định hướng Data Engineering. **Phiên thực nghiệm:** 16/11/2026. **Corpus:** 63 tài liệu, 3.285 đoạn, catalog 85 mục.

Bản nháp này nối tiếp Chương 1 của nhóm, tập trung vào thiết kế và thực nghiệm. Nhóm bổ sung tên trường, giảng viên, thành viên và yêu cầu định dạng của cơ sở đào tạo khi ghép vào bản nộp. Số liệu là kết quả đã ghi nhận; tài nguyên đề xuất được phân biệt với cấu hình thực nghiệm, và các công nghệ chưa triển khai được ghi ở phần hướng phát triển.

[Mục lục đề xuất và dung lượng biên tập](01_MUC_LUC_DE_XUAT.md) · [Bộ biểu đồ riêng](03_BIEU_DO_THONG_KE.md) · [Danh mục dữ liệu và truy vấn](PHU_LUC_DANH_MUC_DU_LIEU.md) · [Hướng dẫn tái tạo](README.md).

---

'''
    source_md=intro+'\n\n'.join((OUT/name).read_text(encoding='utf-8') for name in ['chuong_2.md','chuong_3.md','TAI_LIEU_THAM_KHAO.md'])
    source_md+='\n\n# PHỤ LỤC VÀ BẰNG CHỨNG\n\nDanh mục toàn bộ 63 tài liệu và 15 câu hỏi nằm trong [phụ lục dữ liệu](PHU_LUC_DANH_MUC_DU_LIEU.md). Số liệu từng tài liệu/đoạn nằm trong [document_statistics.csv](evidence/document_statistics.csv) và [chunk_statistics.csv](evidence/chunk_statistics.csv). [Danh mục hình](DANH_MUC_HINH.md) cung cấp ảnh, SVG và nguồn tương ứng.\n'
    (OUT/'02_BAN_NHAP_CHUONG_2_3.md').write_text(source_md,encoding='utf-8')
    charts=json.loads((E/'chart_manifest.json').read_text(encoding='utf-8'))
    gallery=['# BỘ BIỂU ĐỒ THỐNG KÊ DỮ LIỆU VÀ THỰC NGHIỆM',
        '\n16 biểu đồ từ dữ liệu thật, mỗi hình có PNG 300 dpi và SVG. Phông Times New Roman; màu xanh đậm, vàng và xanh lá thống nhất với báo cáo. [Về bản nháp](02_BAN_NHAP_CHUONG_2_3.md).']
    for c in charts:
        name=c['file'];stem=Path(name).stem
        gallery += ['\n## '+c['title'],f"\n![{c['title']}](hinh_anh/{name})",'\n'+c['caption'],
            f"\n[PNG](hinh_anh/{name}) · [SVG](hinh_anh/{stem}.svg) · Nguồn: `{c['source']}`."]
    (OUT/'03_BIEU_DO_THONG_KE.md').write_text('\n'.join(gallery)+'\n',encoding='utf-8')
    images=sorted((OUT/'hinh_anh').glob('hinh_*.png'))
    index=['# DANH MỤC HÌNH VÀ NGUỒN',
        '\n10 sơ đồ thiết kế + 16 biểu đồ + 14 ảnh chụp ứng dụng/hạ tầng = 40 hình. Số hình 3.30 được bổ sung để giải thích các giá trị bằng 0 ở cấp thư mục HDFS.','\n| Hình | PNG | SVG / nguồn chỉnh sửa |','|---|---|---|']
    for p in images:
        svg=p.with_suffix('.svg');dot=OUT/'so_do'/p.with_suffix('.dot').name
        other=[]
        if svg.exists():other.append(f'[SVG](hinh_anh/{svg.name})')
        if dot.exists():other.append(f'[Graphviz](so_do/{dot.name})')
        if not other:other.append('[Manifest ảnh chụp](evidence/screenshot_manifest.json)')
        index.append(f'| {p.stem} | [PNG](hinh_anh/{p.name}) | '+ ' · '.join(other)+' |')
    (OUT/'DANH_MUC_HINH.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
    render(source_md,'02_BAN_NHAP_CHUONG_2_3.html','Bản nháp báo cáo Chương 2–3')
    render('\n'.join(gallery),'03_BIEU_DO_THONG_KE.html','Biểu đồ dữ liệu và thử nghiệm')
    render('\n'.join(appendix),'PHU_LUC_DANH_MUC_DU_LIEU.html','Danh mục dữ liệu')
    # QA: all relative Markdown links must resolve, including report source links.
    missing=[]
    for f in OUT.glob('*.md'):
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',f.read_text(encoding='utf-8')):
            if link.startswith(('http://','https://','#','mailto:')):continue
            path=link.split('#',1)[0].strip('<>')
            if path and not (f.parent/path).exists():missing.append((f.name,path))
    assets=[]
    for p in images:
        with Image.open(p) as im:im.verify()
        with Image.open(p) as im:dimensions=im.size
        assets.append({'file':'hinh_anh/'+p.name,'width':dimensions[0],'height':dimensions[1],
            'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    assert len(images)==40,(len(images),'Expected 10 diagrams + 16 charts + 14 captures')
    (E/'report_asset_manifest.json').write_text(json.dumps(assets,ensure_ascii=False,indent=2),encoding='utf-8')
    missing=[(name,path) for name,path in missing if not (OUT/path).exists()]
    assert not missing,missing
    # Contact sheets are QA evidence only, not screenshots of the application.
    for start in range(0,len(images),12):
        group=images[start:start+12];sheet=Image.new('RGB',(1500,410*((len(group)+2)//3)),'#e9edf0');draw=ImageDraw.Draw(sheet)
        font=ImageFont.truetype('C:/Windows/Fonts/times.ttf',18)
        for j,p in enumerate(group):
            with Image.open(p) as im:
                im=im.convert('RGB');im.thumbnail((480,365))
                x=(j%3)*500+(500-im.width)//2;y=(j//3)*410+30
                sheet.paste(im,(x,y));draw.text(((j%3)*500+8,(j//3)*410+5),p.stem,font=font,fill='#173e59')
        sheet.save(E/f'contact_sheet_{start//12+1}.jpg',quality=88)
    print(json.dumps({'figures':len(images),'charts':len(charts),'documents':len(catalog),
        'relative_links':'all valid','markdown_characters':len(source_md),'markdown_words':len(source_md.split())},ensure_ascii=False))


if __name__=='__main__':main()
