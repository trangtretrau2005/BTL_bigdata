"""Export measured corpus/experiment charts, never synthetic report numbers."""
from pathlib import Path
import csv
import json
import re
import statistics
import sys
import textwrap
import wave
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/report_tools'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
E = ROOT / 'docs/bao_cao/evidence'
OUT = ROOT / 'docs/bao_cao/hinh_anh'
BLUE, GOLD, GREEN, RED = '#173e59', '#c49232', '#37836f', '#ad4c4c'
PALETTE = [BLUE, GOLD, GREEN, '#647dad', '#af7a70', '#8f8b52', '#826b93']
font = Path('C:/Windows/Fonts/times.ttf')
if font.exists():
    font_manager.fontManager.addfont(str(font))
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams.update({'font.size':12,'axes.titlesize':17,'axes.labelsize':12,
    'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white',
    'axes.facecolor':'white','svg.fonttype':'none','savefig.facecolor':'white'})


def load(name):
    return json.loads((E/name).read_text(encoding='utf-8-sig'))


def read_csv(name):
    with (E/name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


MANIFEST = []
def finish(fig, name, title, caption, source='document_statistics.csv'):
    fig.suptitle(title, fontweight='bold', color=BLUE, y=.97)
    fig.text(.02,.025,textwrap.fill(caption,118),fontsize=10,color='#4a5361',va='bottom')
    fig.tight_layout(rect=(.01,.16,.99,.91))
    for ext in ['png','svg']:
        fig.savefig(OUT/(name+'.'+ext),dpi=300)
    MANIFEST.append({'file':name+'.png','title':title,'caption':caption,'source':'evidence/'+source})
    plt.close(fig)


def bars(name,title,items,caption,xlabel='Số văn bản',source='document_statistics.csv'):
    labels, values = zip(*items)
    fig,ax=plt.subplots(figsize=(10,8.5 if len(values)>8 else 6))
    ax.barh(labels,values,color=PALETTE[:len(values)] if len(values)<=7 else BLUE,height=.62)
    ax.invert_yaxis();ax.set_xlabel(xlabel);ax.set_xlim(0,max(values)*1.23)
    ax.xaxis.grid(True,alpha=.17);ax.set_axisbelow(True)
    for i,v in enumerate(values):ax.text(v+max(values)*.02,i,f'{v:,}'.replace(',','.'),va='center',fontweight='bold',color=BLUE)
    finish(fig,name,title,caption,source)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    docs=read_csv('document_statistics.csv');chunks=read_csv('chunk_statistics.csv')
    facts=load('system_facts.json');q=facts['quality']
    assert len(docs)==63 and len(chunks)==3285, 'Reconcile report text if production corpus changes.'
    bars('hinh_3_12_khu_vuc','Phân bố 63 văn bản theo nhãn khu vực',
        [(label,q['regions'].get(key,0)) for label,key in [('Việt Nam','VN'),('Quốc tế / các quốc gia khác','INTERNATIONAL'),('Hoa Kỳ','US'),('Liên minh châu Âu','EU'),('ASEAN','ASEAN')]],
        'Nguồn: snapshot đang hoạt động, 16/11/2026. INTERNATIONAL là nhãn gộp trong dữ liệu, không phải một quốc gia.')
    fig,ax=plt.subplots(figsize=(9,6))
    counts=Counter(r['language'] for r in docs)
    ax.pie([counts['vi'],counts['en']],labels=['Tiếng Việt','Tiếng Anh'],colors=[BLUE,GOLD],
        autopct=lambda p:f'{p*len(docs)/100:.0f} văn bản\n({p:.1f}%)',pctdistance=.74,
        wedgeprops={'width':.45,'edgecolor':'white'},textprops={'fontsize':13})
    ax.text(0,0,'63\nvăn bản',ha='center',va='center',fontsize=20,fontweight='bold',color=BLUE)
    finish(fig,'hinh_3_13_ngon_ngu','Hai ngôn ngữ trong corpus hiện tại',
        'Đếm theo trường language của văn bản; chưa đánh giá riêng chất lượng hỏi đáp xuyên ngôn ngữ.')
    types={'regulation':'Quy định / nghị định','guideline':'Hướng dẫn','framework':'Khung quản trị',
        'policy':'Chính sách','law':'Luật','strategy':'Chiến lược','recommendation':'Khuyến nghị'}
    bars('hinh_3_14_loai_van_ban','Cơ cấu loại tài liệu',
        [(types.get(k,k),v) for k,v in Counter(r['document_type'] for r in docs).most_common()],
        'Loại tài liệu là nhãn chuẩn hóa phục vụ lọc; không dùng để tự xác nhận giá trị hay hiệu lực pháp lý.')
    fig,axes=plt.subplots(1,2,figsize=(11,6))
    for ax,key,total,label in [(axes[0],'provenance_documents',63,'Văn bản'),(axes[1],'provenance_chunks',3285,'Đoạn')]:
        vals=[q[key].get('official_download',0),q[key].get('official_api',0)]
        ax.bar(['Tải nguồn\nchính thức','API Bộ Tư pháp'],vals,color=[BLUE,GOLD],width=.55)
        ax.set_title(f'{label}: {total:,}'.replace(',','.'));ax.set_ylim(0,max(vals)*1.27)
        for i,v in enumerate(vals):ax.text(i,v+max(vals)*.025,f'{v:,}\n{v/total:.1%}'.replace(',','.'),ha='center')
        ax.yaxis.grid(True,alpha=.15);ax.set_axisbelow(True)
    finish(fig,'hinh_3_15_nguon_thu_thap','Nguồn thu thập và đóng góp vào chỉ mục',
        'API đóng góp 17/63 văn bản và 325/3.285 đoạn. Đây là dữ liệu đã công bố, không phải toàn bộ kết quả API quét được.','system_facts.json')
    years=Counter()
    for d in docs:
        m=re.search(r'\b(?:19|20)\d{2}\b',d['published_date'])
        years[m.group(0) if m else 'Thiếu ngày']+=1
    fig,ax=plt.subplots(figsize=(10,6));labels=sorted(k for k in years if k!='Thiếu ngày')+['Thiếu ngày']
    vals=[years[k] for k in labels];ax.bar(labels,vals,color=[BLUE if k!='Thiếu ngày' else GOLD for k in labels])
    ax.set_ylabel('Số văn bản');ax.set_ylim(0,max(vals)*1.2)
    for i,v in enumerate(vals):ax.text(i,v+.3,str(v),ha='center')
    finish(fig,'hinh_3_16_nam_ban_hanh','Năm ban hành theo metadata hiện có',
        f"Có {years.get('Thiếu ngày',0)}/63 tài liệu thiếu published_date; không suy diễn năm từ tên tệp hoặc tiêu đề.")
    sizes=[int(d['characters']) for d in docs]
    fig,ax=plt.subplots(figsize=(10,6));bins=[0,10_000,30_000,100_000,300_000,1_000_000,3_000_000]
    hist=np.histogram(sizes,bins=bins)[0];labels=['< 10 nghìn','10–30 nghìn','30–100 nghìn','100–300 nghìn','0,3–1 triệu','1–3 triệu']
    ax.bar(labels,hist,color=BLUE);ax.set_ylabel('Số văn bản');ax.set_xlabel('Độ dài văn bản sau ETL (ký tự)')
    for i,v in enumerate(hist):ax.text(i,v+.25,str(v),ha='center')
    finish(fig,'hinh_3_17_do_dai_van_ban','Độ dài văn bản không đồng đều',
        f'Tổng {sum(sizes):,} ký tự; trung vị {statistics.median(sizes):,.0f} ký tự. Ký tự không đồng nghĩa với token.'.replace(',','.'))
    lengths=[int(c['characters']) for c in chunks]
    fig,ax=plt.subplots(figsize=(10,6));ax.hist(lengths,bins=30,color=BLUE,edgecolor='white')
    ax.axvline(q['chunk_characters_median'],color=GOLD,lw=2,label='Trung vị: 2.109')
    ax.axvline(q['chunk_characters_p95'],color=GREEN,lw=2,ls='--',label='P95: 2.194')
    ax.set_xlabel('Số ký tự / đoạn');ax.set_ylabel('Số đoạn');ax.legend()
    finish(fig,'hinh_3_18_do_dai_chunk','Phân bố độ dài 3.285 đoạn',
        'Cấu hình tối đa 2.200 ký tự, chồng lấn 240; ưu tiên ranh giới điều/câu nên độ dài không cố định.','chunk_statistics.csv')
    top=sorted(docs,key=lambda d:int(d['chunks']),reverse=True)[:10]
    bars('hinh_3_19_top_tai_lieu','Mười tài liệu đóng góp nhiều đoạn nhất',
        [(textwrap.fill(textwrap.shorten(d['title'],width=85,placeholder='…'),44),int(d['chunks'])) for d in top],
        'Đếm theo source_document_id. Tài liệu dài có thể chi phối kết quả truy xuất nếu thiếu lọc và xếp hạng bổ sung.',xlabel='Số đoạn')
    # Taller figure for wrapped titles.
    known_dates=sum(bool(re.search(r'\b(?:19|20)\d{2}\b',d['published_date'])) for d in docs)
    fig,ax=plt.subplots(figsize=(10,6))
    categories=['Nguồn tài liệu','Nguồn đoạn','Phiên bản đoạn','ID đoạn duy nhất','Ngày ban hành tài liệu']
    valid=[len(docs)-q['missing_document_source'],len(chunks)-q['missing_chunk_source'],
        len(chunks)-q['missing_chunk_version'],len(chunks)-q['duplicate_chunk_ids'],known_dates]
    den=[len(docs),len(chunks),len(chunks),len(chunks),len(docs)]
    percentages=[100*v/n for v,n in zip(valid,den)]
    ax.barh(categories,percentages,color=[BLUE]*4+[GOLD]);ax.invert_yaxis();ax.set_xlim(0,124);ax.set_xlabel('Tỷ lệ đầy đủ / hợp lệ (%)')
    for i,(p,v,n) in enumerate(zip(percentages,valid,den)):ax.text(p+1,i,f'{v}/{n} ({p:.1f}%)',va='center')
    finish(fig,'hinh_3_20_chat_luong_metadata','Kiểm tra độ đầy đủ và định danh',
        'Đủ metadata chỉ xác nhận khả năng truy vết; không chứng minh nội dung pháp luật đúng hay còn hiệu lực.','system_facts.json; document_statistics.csv')
    bars('hinh_3_21_trang_thai_danh_muc','Danh mục nguồn và tài liệu đang tra cứu',
        [('Đang tra cứu',63),('Chưa lập chỉ mục',22)],
        '63 + 22 = 85 mục danh mục. Chưa lập chỉ mục gồm nguồn chưa tải/parse/kiểm tra thành công; không mặc định tất cả đều lỗi.')
    etl=load('etl_scaling_results.json')['runs'];groups=defaultdict(list)
    for r in etl:groups[r['input_rows']].append(r['elapsed_seconds'])
    x=sorted(groups);means=[statistics.mean(groups[k]) for k in x]
    fig,ax=plt.subplots(figsize=(10,6))
    ax.errorbar(x,means,yerr=[[m-min(groups[k]) for k,m in zip(x,means)],[max(groups[k])-m for k,m in zip(x,means)]],
        fmt='o-',color=BLUE,capsize=7,lw=2)
    ax.set_xticks(x);ax.set_ylim(0,max(max(v) for v in groups.values())*1.22)
    ax.set_xlabel('Số bản ghi đầu vào (nhân lặp corpus)');ax.set_ylabel('Thời gian Spark ETL (giây)')
    for k,m in zip(x,means):ax.text(k,m+.6,f'{m:.2f} s',ha='center',fontweight='bold')
    finish(fig,'hinh_3_22_etl_quy_mo','ETL với dữ liệu lặp: 3 lần đo / mức',
        'Spark local[2]; chấm = trung bình, thanh = min–max. Cả ba mức đều cho 63 nội dung duy nhất. Warmup được loại.','etl_scaling_results.json')
    retrieval=load('retrieval_results.json');cases=[r for r in retrieval['details'] if r['repeat']==1]
    fig,ax=plt.subplots(figsize=(11,6));ranks=[r['rank'] if r['rank'] else 6 for r in cases]
    ax.bar([r['case_id'] for r in cases],ranks,color=[GREEN if v==1 else GOLD if v<=5 else RED for v in ranks])
    ax.set_yticks([1,2,3,4,5,6],['1','2','3','4','5','Ngoài top 5']);ax.set_ylim(0,7.2)
    ax.set_ylabel('Vị trí đầu tiên của tài liệu kỳ vọng');ax.set_xlabel('Mã câu hỏi (xem bảng truy vấn trong phụ lục)')
    finish(fig,'hinh_3_23_xep_hang','Kết quả truy xuất trên 15 câu hỏi chọn thủ công',
        'Hit@1 = 73,3%; Hit@5 = 93,3%; MRR@5 = 0,833. R13 chưa tìm đúng OECD trong top 5. Không phải độ chính xác pháp lý.','retrieval_results.json')
    llm=load('llm_smoke.json')['answers'];times=[r['elapsed_seconds'] for r in llm]
    fig,ax=plt.subplots(figsize=(10,6));ax.bar(['Phạm vi Luật AI\nLLM sinh','NIST AI RMF\nLLM sinh','Điều 5 EU AI Act\nTóm tắt biên tập'],times,color=[BLUE,BLUE,GOLD])
    ax.set_ylabel('Thời gian đầu cuối (giây)');ax.set_ylim(0,max(times)*1.25)
    for i,v in enumerate(times):ax.text(i,v+.5,f'{v:.2f} s',ha='center',fontweight='bold')
    finish(fig,'hinh_3_24_thoi_gian_hoi_dap','Ba ca kiểm tra chức năng đầu cuối',
        'Hai ca dùng Qwen3 Instruct; ca EU dùng bản biên tập có điều kiện checksum. Mỗi ca một lần, không kết luận hiệu năng tổng quát.','llm_smoke.json')
    zones=Counter()
    for f in facts['latest_sync']['files']:
        parts=f['path'].strip('/').split('/');zones[parts[1]]+=int(f['bytes'])
    fig,ax=plt.subplots(figsize=(10,6));items=zones.most_common();vals=[v/1048576 for _,v in items]
    ax.bar([k for k,_ in items],vals,color=PALETTE[:len(items)]);ax.set_ylabel('MiB (1 MiB = 1.048.576 byte)');ax.set_ylim(0,max(vals)*1.22)
    for i,v in enumerate(vals):ax.text(i,v+max(vals)*.025,f'{v:.2f}',ha='center')
    finish(fig,'hinh_3_25_cac_lop_data_lake','Dung lượng các lớp trong lượt đồng bộ gần nhất',
        '178 tệp, 106.031.673 byte; đây là manifest một lượt đồng bộ, không phải toàn bộ namespace HDFS có lịch sử.','system_facts.json → latest_sync')
    statuses=Counter(d['legal_status'] or 'unknown' for d in docs)
    bars('hinh_3_26_trang_thai_phap_ly','Trạng thái pháp lý theo metadata đã lưu',
        [(k,v) for k,v in statuses.most_common()],
        'Nhãn từ dữ liệu nguồn, chưa thẩm định lại toàn bộ tại ngày đo. unknown / Chưa xác định không đồng nghĩa còn hiệu lực.')
    voice=load('presenter_browser_check.json')
    wavs=[f for f in voice.get('audio_files',[]) if f['mime']=='audio/wav']
    if wavs:
        fig,axes=plt.subplots(len(wavs),1,figsize=(11,6),squeeze=False)
        for i,f in enumerate(wavs):
            with wave.open(str(ROOT/'docs/bao_cao'/f['file'])) as w:
                rate=w.getframerate();samples=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)/32768
            ax=axes[i,0];stride=max(1,len(samples)//14000)
            ax.plot(np.arange(len(samples))[::stride]/rate,samples[::stride],color=BLUE,lw=.6)
            ax.set_ylim(-1,1);ax.set_ylabel(f'Đoạn {i+1}\nBiên độ chuẩn hóa');ax.set_xlabel('Thời gian (giây)')
            ax.set_title(f"{f['duration_seconds']:.2f} s · {f['sample_rate']:,} Hz · {f['channels']} kênh".replace(',','.'))
            ax.yaxis.grid(True,alpha=.15)
        finish(fig,'hinh_3_29_song_am','Sóng âm thật của hai đoạn người thuyết trình',
            f"Provider thực tế: {voice['provider']}; trích PCM từ WAV đã phát trong trình duyệt. Hình dạng sóng không chứng minh độ tự nhiên của giọng.",'presenter_browser_check.json; am_thanh/*.wav')
    (E/'chart_manifest.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2),encoding='utf-8')
    stats={'published_years':dict(years),'document_length_min':min(sizes),'document_length_median':statistics.median(sizes),
        'document_length_max':max(sizes),'top_document_chunks':[(d['source_document_id'],int(d['chunks'])) for d in top],
        'legal_status':dict(Counter(d['legal_status'] or 'unknown' for d in docs)), 'sync_zone_bytes':dict(zones)}
    (E/'derived_statistics.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Exported {len(MANIFEST)} charts as PNG + SVG.')


if __name__=='__main__':main()
