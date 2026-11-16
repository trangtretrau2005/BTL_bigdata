"""Render editable Graphviz sources into report SVG and PNG figures."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/bao_cao/so_do'
FIG=ROOT/'docs/bao_cao/hinh_anh'


def diagram(name,title,nodes,edges,*,direction='TB',groups=None):
    OUT.mkdir(parents=True,exist_ok=True);FIG.mkdir(parents=True,exist_ok=True)
    lines=['digraph G {',f'graph [rankdir={direction}, bgcolor="white", pad="0.35", nodesep="0.30", ranksep="0.45", splines=polyline, fontname="Liberation Serif", fontsize=20, label={json.dumps(title,ensure_ascii=False)}, labelloc=t];',
        'node [shape=box, style="rounded,filled", fillcolor="#F2F6F8", color="#31576B", fontcolor="#142C3A", fontname="Liberation Serif", fontsize=13, margin="0.16,0.11"];',
        'edge [color="#56717F", arrowsize=0.7, fontname="Liberation Serif", fontsize=11, fontcolor="#4B5962"];']
    for key,value in nodes.items():
        label,kind=(value if isinstance(value,tuple) else (value,'process'))
        attrs={'label':label}
        if kind=='decision':attrs.update(shape='diamond',style='filled',fillcolor='#FFF5DA')
        elif kind=='store':attrs.update(shape='cylinder',fillcolor='#E6EFE9',color='#3B7565')
        elif kind=='end':attrs.update(shape='ellipse',fillcolor='#193E51',fontcolor='white')
        elif kind=='error':attrs.update(fillcolor='#FBEDE9',color='#AB6453')
        lines.append(key+' ['+', '.join(k+'='+json.dumps(v,ensure_ascii=False) for k,v in attrs.items())+'];')
    if groups:
        for i,(label,keys) in enumerate(groups):
            lines.append(f'subgraph cluster_{i} {{ label={json.dumps(label,ensure_ascii=False)}; color="#D0DADF"; style="rounded"; '+ ';'.join(keys)+'; }')
    for edge in edges:
        a,b,*label=edge
        lines.append(f'{a} -> {b}'+ (' [label='+json.dumps(label[0],ensure_ascii=False)+']' if label else '')+';')
    lines.append('}')
    source=OUT/(name+'.dot');source.write_text('\n'.join(lines),encoding='utf-8')
    for ext in ['svg','png']:
        subprocess.run(['dot','-T'+ext,'-Gdpi=160',str(source),'-o',str(FIG/(name+'.'+ext))],check=True)


def main():
    diagram('hinh_2_01_kien_truc','Kiến trúc logic của nền tảng',{
        's':'BA KÊNH DỮ LIỆU\nNguồn chính thức PDF/HTML · API Bộ Tư pháp\nUpload PDF / DOCX / TXT / HTML / XML',
        'w':'TIẾP NHẬN VÀ ĐIỀU PHỐI\nWorker nền + khóa + parser\nBronze / Parsed + hash + provenance',
        'e':'ETL VÀ BẢNG DỮ LIỆU\nSpark local[2]: làm sạch / chuẩn hóa / khử trùng\nSilver: Parquet theo phiên bản',
        'c':'CHUẨN BỊ CHỈ MỤC\nChunk 2.200 ký tự / overlap 240\nBGE-M3 dense 1.024 chiều, batch 8',
        'q':('GOLD / SERVING\nQdrant snapshot hoàn chỉnh\nAlias ổn định + payload nguồn','store'),
        'i':'KHAI THÁC TRÊN STREAMLIT\nThư viện / tìm kiếm / hỏi đáp RAG\nTruy xuất → Qwen3 Instruct → kiểm tra trích dẫn',
        'ans':'TRẢI NGHIỆM NGƯỜI DÙNG\nCâu trả lời + nguồn / tải bản gốc\nTTS + phụ đề + người thuyết trình nữ',
        'h':('HDFS QUA WEBHDFS\nBản gốc / Parsed / Parquet / Chunks\nLưu theo lớp và phiên bản','store'),
        'm':('METADATA VÀ QUAN SÁT\nCatalog / checkpoint / manifest\nTiến độ job / lỗi / báo cáo chất lượng','store')},
        [('s','w'),('w','e'),('e','c'),('c','q'),('q','i'),('i','ans'),('w','h'),('e','h'),('c','h'),('w','m'),('m','i','phiên bản + trạng thái')],direction='TB')
    diagram('hinh_2_02_flowchart_toan_bo','Flowchart tổng thể vòng đời dữ liệu và phục vụ tra cứu',{
        'start':('Mở ứng dụng','end'),'choice':('Thao tác của người dùng?','decision'),
        'upd':'Bấm Cập nhật dữ liệu','lock':('Có lượt khác đang chạy?','decision'),'busy':'Theo dõi lượt hiện tại',
        'save':'Kiểm tra và lưu tệp được chọn\nHash + metadata nguồn người dùng','parse':'Trích xuất tệp hợp lệ\nTách lỗi theo từng tệp',
        'api':('Bật lấy dữ liệu API?','decision'),'fetch':'Danh mục phân trang mới nhất\nCheckpoint + khoảng chồng 7 ngày',
        'full':'Lọc chủ đề/ngày + lấy toàn văn\nLưu JSON bất biến + phiên bản','merge':'Ghép corpus đã xác minh\nAPI + tệp người dùng hợp lệ',
        'change':('Chữ ký corpus thay đổi?','decision'),'same':'Không lập chỉ mục lại\nTrả no_changes / partial',
        'etl':'Spark ETL → Parquet Silver\nChuẩn hóa + chất lượng + khử trùng','chunks':'Chia đoạn theo điều/đoạn/câu\nGiữ nguồn + vị trí + phiên bản',
        'embed':'Tái sử dụng vector không đổi\nEmbedding các đoạn còn thiếu','snap':('Snapshot Qdrant mới','store'),
        'check':('Đủ point dự kiến?','decision'),'old':('Giữ alias và manifest cũ\nGhi lỗi / cho chạy lại','error'),
        'publish':'Đổi alias nguyên tử\nGhi manifest phiên bản đang dùng','lake':'Đồng bộ các lớp lên HDFS\nĐối chiếu kích thước tệp',
        'refresh':'Cập nhật số đếm / trạng thái\nSẵn sàng tìm tài liệu mới','query':'Nhận câu hỏi + bộ lọc\nKiểm tra phạm vi',
        'retrieve':'BGE-M3 → tìm Qdrant\nTop-k + mở rộng điều phù hợp','enough':('Có bằng chứng đủ điểm?','decision'),
        'refuse':'Thông báo thiếu căn cứ','generate':'LLM hoặc bản biên tập có hash\nPhân biệt rõ chế độ trả lời',
        'valid':('Nhãn trích dẫn hợp lệ?','decision'),'retry':'Thử sửa đầu ra tối đa một lần\nLỗi thì báo chưa thể trả lời',
        'answer':'Hiển thị câu trả lời / đoạn nguồn\nLiên kết hoặc tải tệp gốc','mode':('Chế độ hiện tại?','decision'),
        'search':'Hiển thị các đoạn tìm thấy\nKhông gọi LLM','library':'Đọc catalog / manifest\nLọc, phân trang và mở nguồn',
        'read':('Người dùng yêu cầu nghe?','decision'),'tts':'Chuẩn hóa văn bản → TTS\nPlaylist / nhãn provider thực tế',
        'voice':'Người thuyết trình nữ\nPhụ đề + miệng theo biên độ + phát',
        'qend':('Kết thúc tra cứu','end'),'lend':('Kết thúc xem danh mục','end'),'end':('Kết thúc cập nhật','end')},
        [('start','choice'),('choice','upd','cập nhật'),('choice','query','hỏi / tìm'),('choice','library','thư viện'),('library','lend'),('upd','lock'),('lock','busy','có'),('busy','end'),
         ('lock','save','không'),('save','parse'),('parse','api'),('api','fetch','có'),('fetch','full'),('full','merge'),('api','merge','không'),
         ('merge','change'),('change','same','không'),('same','refresh'),('change','etl','có'),('etl','chunks'),('chunks','embed'),('embed','snap'),
         ('snap','check'),('check','old','không / lỗi'),('check','publish','có'),('old','end'),('publish','lake'),('lake','refresh'),('refresh','end'),
         ('query','retrieve'),('retrieve','mode'),('mode','search','tìm kiếm'),('mode','enough','hỏi đáp'),('search','qend'),('enough','refuse','không'),('enough','generate','có'),('generate','valid'),('valid','retry','không'),
         ('retry','qend'),('valid','answer','có'),('refuse','qend'),('answer','read'),('read','qend','không'),('read','tts','có'),('tts','voice'),('voice','qend')])
    diagram('hinh_2_03_api_dong','Thu thập tăng dần qua API Bộ Tư pháp',{
        's':('Bắt đầu nguồn API','end'),'cfg':'Đọc cấu hình nguồn\nTừ khóa + số trang + giới hạn',
        'cp':('Đã có checkpoint hoàn tất?','decision'),'first':'Cửa sổ ban đầu 730 ngày','next':'Từ checkpoint trừ 7 ngày',
        'list':'POST /doc/all\nPhân trang, issueDate giảm dần','ok':('Cấu trúc danh mục hợp lệ?','decision'),
        'raw':('Lưu JSON catalog theo SHA-256','store'),'filter':'Lọc ngày / chủ đề AI\nKhông nhận ngày tương lai','known':('Metadata đã kiểm tra hôm nay?','decision'),
        'skip':'Bỏ qua toàn văn không đổi','limit':('Đạt giới hạn thay đổi?','decision'),'backlog':'Ghi còn dữ liệu chờ lượt sau',
        'detail':'GET /doc/{id}\ndocumentContent.content','body':('Toàn văn thật, đủ dài?','decision'),
        'reject':('Ghi lỗi / loại trang chặn\nKhông dùng abstract hay aiResults','error'),
        'canon':'Ghép số hiệu + cơ quan + năm\nTái sử dụng ID văn bản đã có','hash':'Hash nội dung + lưu Raw/Parsed\nCập nhật catalog và trạng thái',
        'more':('Còn trang trong cửa sổ?','decision'),'done':('Nguồn không lỗi / không backlog?','decision'),
        'write':'Nâng checkpoint hoàn tất','keep':'Giữ checkpoint trước\nLượt sau kiểm tra lại phần thiếu','e':('Trả báo cáo cho worker','end')},
        [('s','cfg'),('cfg','cp'),('cp','first','chưa'),('cp','next','có'),('first','list'),('next','list'),('list','ok'),('ok','reject','không'),('ok','raw','có'),
         ('raw','filter'),('filter','known'),('known','skip','có'),('known','limit','chưa'),('limit','backlog','có'),('limit','detail','chưa'),('detail','body'),
         ('body','reject','không'),('body','canon','có'),('canon','hash'),('hash','more'),('skip','more'),('backlog','more'),('reject','more'),
         ('more','list','có'),('more','done','không'),('done','write','có'),('done','keep','không'),('write','e'),('keep','e')])
    diagram('hinh_2_04_upload','Tiếp nhận và lập chỉ mục tệp người dùng',{
        's':('Chọn tệp trên giao diện','end'),'click':'Chọn khu vực / ngôn ngữ\nBấm Cập nhật dữ liệu','valid':('Loại, chữ ký, kích thước hợp lệ?','decision'),
        'bad':('Hiển thị lỗi; không lưu lô lỗi định dạng','error'),'hash':'SHA-256 nội dung tệp\nID upload_<hash>','exists':('Đã lưu cùng checksum?','decision'),
        'reuse':'Giữ ID và tên đã lưu\nSửa bản gốc nếu hỏng/mất','raw':('Lưu tệp gốc + catalog\nprovenance=user_upload','store'),
        'parse':'Parser PDF / DOCX / TXT / HTML / XML','text':('Có văn bản đủ dài?','decision'),'scan':('Báo scan/không đọc được\nKhông đưa nội dung rỗng vào ETL','error'),
        'parsed':('Parsed JSON + tên tệp gốc\nHiệu lực unknown','store'),'pipeline':'Ghép corpus → Spark → chia đoạn\nEmbedding → snapshot mới',
        'dup':('Nội dung bị Spark khử trùng?','decision'),'known':'Nội dung đã có trong thư viện\nGắn duplicate_of','indexed':'Đánh dấu đã lập chỉ mục\nCó thể chọn để hỏi đáp',
        'lake':'Đồng bộ Raw/Parsed và phiên bản\nSilver/Chunks lên HDFS','source':'Dẫn chứng giữ original_filename\nNút Tải tệp gốc','e':('Kết thúc','end')},
        [('s','click'),('click','valid'),('valid','bad','không'),('valid','hash','có'),('hash','exists'),('exists','reuse','có'),('exists','raw','chưa'),
         ('reuse','parse'),('raw','parse'),('parse','text'),('text','scan','không'),('text','parsed','có'),('parsed','pipeline'),('pipeline','dup'),('dup','known','có'),
         ('dup','indexed','không'),('known','lake'),('indexed','lake'),('lake','source'),('source','e'),('bad','e'),('scan','e')])
    diagram('hinh_2_05_etl','Thiết kế ETL bằng Spark DataFrame',{
        's':('Parsed JSON từ các kênh','store'),'schema':'Đọc schema, hợp nhất trường tương đương\ntext / content / body; url; region',
        'clean':'Chuẩn hóa khoảng trắng / xuống dòng\nGiữ nội dung + metadata nguồn','length':('text khác null và ≥ 30 ký tự?','decision'),
        'drop':('Loại bản ghi không hợp lệ','error'),'region':'Chuẩn hóa region, jurisdiction\nGiữ ngôn ngữ và provenance',
        'hash':'text_sha256 = SHA256(text)\ndocument_id = SHA256(ID nguồn | URL | hash)',
        'window':'Window partitionBy(text_sha256)\norderBy(URL, title, source_path)',
        'dedup':'row_number = 1\nMột đại diện cho nội dung giống hệt','stats':'Đếm đầu vào / hợp lệ / loại-trùng\nPhân bố vùng, loại và số ký tự',
        'write':('Ghi Parquet Silver theo job_id\nCodec mặc định được kiểm tra thực tế','store'),
        'chunk':'Chia đoạn bằng Python/PyArrow\nƯu tiên điều → đoạn → câu',
        'gold':('JSONL + Parquet các chunk\nID ổn định + vị trí + nguồn','store')},
        [('s','schema'),('schema','clean'),('clean','length'),('length','drop','không'),('length','region','có'),('region','hash'),('hash','window'),
         ('window','dedup'),('dedup','stats'),('stats','write'),('write','chunk'),('chunk','gold')])
    diagram('hinh_2_06_rag','Luồng hỏi đáp có kiểm tra nguồn',{
        's':('Câu hỏi + region/document filter','end'),'scope':('Đúng phạm vi hoặc đã chọn tài liệu?','decision'),'no':'Thiếu căn cứ / ngoài phạm vi',
        'emb':'BGE-M3 embedding câu hỏi','search':'Qdrant cosine search\nTop-k, điều kiện payload','article':'Nếu hỏi phạm vi/hành vi cấm:\nđọc đúng điều trong Silver đang dùng',
        'score':('Có nguồn có text + URL và score ≥ ngưỡng?','decision'),
        'cur':('Có bản biên tập khớp ID và hash toàn điều?','decision'),
        'editor':'Trả curated_summary\nmodel=null, nhãn biên tập rõ ràng',
        'prompt':'Prompt tiếng Việt + các nguồn [S1..Sk]\nNội dung tài liệu không phải chỉ thị',
        'llm':'Qwen3 4B Instruct\nnum_ctx=6144, num_predict=640',
        'ref':('LLM báo không đủ bằng chứng?','decision'),
        'cite':('Nhãn nguồn hợp lệ và đủ trích dẫn?','decision'),
        'retry':'Tạo lại tối đa một lần\nNếu vẫn lỗi: báo lỗi dịch vụ/đầu ra',
        'ans':'Hiển thị trả lời + trích đoạn + vị trí\nURL hoặc tải tệp gốc','tts':'Tùy chọn nghe câu trả lời\nMột cấu hình giọng nữ','e':('Kết thúc','end')},
        [('s','scope'),('scope','no','không'),('scope','emb','có'),('emb','search'),('search','article'),('article','score'),('score','no','không'),
         ('score','cur','có'),('cur','editor','có'),('cur','prompt','không'),('prompt','llm'),('llm','ref'),('ref','no','có'),('ref','cite','không'),
         ('cite','retry','không'),('cite','ans','có'),('editor','ans'),('ans','tts'),('tts','e'),('no','e'),('retry','e')])
    diagram('hinh_2_07_snapshot','Công bố chỉ mục và xử lý lỗi',{
        'old':('Alias A đang trỏ snapshot S0','store'),'input':'Chunks của phiên bản mới V1','s1':('Tạo snapshot S1 riêng','store'),
        'batch':'Nạp theo batch 8\nDùng lại vector khi ID/text/model khớp','complete':('count(S1) = số chunk đầu vào?','decision'),
        'fail':('Giữ S0 / lưu tiến độ lỗi\nCho phép dựng lại staging','error'),
        'alias':'Một yêu cầu đổi alias:\nDelete A + Create A → S1',
        'manifest':'Ghi manifest ready\nGắn Silver/Chunks/Signature V1',
        'hdfs':'Đồng bộ HDFS theo job_id','h_ok':('Đồng bộ thành công?','decision'),
        'partial':'Báo partial do HDFS\nTra cứu vẫn dùng S1 đã công bố',
        'ok':('Báo completed / làm mới UI','end')},
        [('old','input'),('input','s1'),('s1','batch'),('batch','complete'),('complete','fail','không / lỗi'),('complete','alias','có'),
         ('alias','manifest'),('manifest','hdfs'),('hdfs','h_ok'),('h_ok','partial','không'),('h_ok','ok','có')])
    diagram('hinh_2_08_trien_khai','Triển khai Docker trên một máy',{
        'browser':'Trình duyệt người dùng\nlocalhost:8501','host':'Windows 11 + Docker Desktop / WSL2',
        'app':'Container app\nPython 3.11 + Streamlit\nSpark driver local[2] + parser/chunker',
        'ol':'Container Ollama\nBGE-M3 + Qwen3 Instruct','gpu':'GPU NVIDIA RTX 3050 6 GB',
        'qd':('Container Qdrant\nVolume qdrant_data','store'),'nn':'Container NameNode\nWebHDFS 9870 / RPC 9000',
        'dn':('Container DataNode\nVolume dữ liệu HDFS','store'),
        'bind':('Bind mount mã + dữ liệu staging\nThư mục dự án trên Windows','store'),
        'ext':'Internet\nAPI pháp luật / giọng trực tuyến',
        'note':'Một DataNode, replication=1\nKhông có Spark worker cluster / YARN'},
        [('browser','app'),('host','app'),('app','ol'),('ol','gpu'),('app','qd'),('app','nn'),('nn','dn'),('app','dn','upload sau redirect 307'),
         ('app','bind'),('app','ext'),('dn','note')],direction='LR')
    diagram('hinh_2_09_metadata','Liên kết metadata và truy nguyên dữ liệu',{
        'catalog':('Catalog nguồn\ndocument_id, title, URL\nregion, provenance','store'),
        'raw':('Raw snapshot\nchecksum, raw_path\nAPI remote_id / filename','store'),
        'parsed':('Parsed JSON hiện tại\ndocument_id, version_id\ntext, content_hash','store'),
        'silver':('Processed document\ndocument_id băm\nsource_document_id, text_sha256','store'),
        'chunk':('Chunk\nchunk_id, document_id\nversion_id, index, vị trí','store'),
        'vector':('Qdrant point\nUUID từ chunk_id\nvector + payload + model','store'),
        'manifest':('Index manifest\nalias, snapshot, signature\nprocessed_path, chunks_path','store'),
        'job':('Update job\njob_id, stage, progress\nproviders, upload_ids, errors','store')},
        [('catalog','raw','1 nguồn → nhiều bản gốc'),('raw','parsed','trích xuất + giữ đường dẫn'),('parsed','silver','chuẩn hóa / khử trùng'),
         ('silver','chunk','một tài liệu → nhiều đoạn'),('chunk','vector','ID ổn định trong snapshot'),('job','raw','điều phối nạp'),
         ('job','manifest','công bố phiên bản'),('manifest','silver','đường dẫn phiên bản'),('manifest','vector','snapshot đang dùng')],direction='TB')
    diagram('hinh_2_10_nguoi_thuyet_trinh','Thiết kế trợ lý giọng nói và người thuyết trình',{
        'q':'Câu hỏi bằng văn bản\nhoặc thu âm WAV tùy chọn','asr':'Nếu thu âm: nhận dạng vi-VN\nNgười dùng đọc lại / chỉnh câu hỏi',
        'rag':'RAG → câu trả lời có nguồn\nHiển thị ngay phần văn bản','click':('Người dùng bấm tạo giọng?','decision'),
        'clean':'Bỏ Markdown / nhãn [Sx] / URL\nMở rộng AI, LLM, số hiệu phổ biến','key':'Khóa nội dung + voice + rate\nCache 600 giây / tối đa 12 mục UI',
        'neural':'Ưu tiên Hoài My trực tuyến\nChia cụm tối đa 700 ký tự','ok':('Có âm thanh?','decision'),
        'fallback':'Piper dự phòng 240 ký tự/cụm\nSau đó Google 170 nếu cần','result':('Có playlist âm thanh?','decision'),
        'device':'Thử giọng Việt trên thiết bị\nKhông có thì báo rõ','bundle':('Playlist: text + audio_b64 + MIME\nProvider thật + playback_rate','store'),
        'player':'Iframe HTML/JS + SVG nữ\nPhát / tạm dừng / đọc lại / tốc độ','audio':'Audio từng đoạn → Web Audio\nAnalyserNode, fftSize=256',
        'rms':'RMS mẫu thời gian → năng lượng\nCập nhật miệng và sóng âm','subtitle':'Sự kiện ended → đoạn tiếp theo\nĐổi phụ đề theo đoạn âm thanh',
        'done':('Đã đọc xong / dừng\nHủy hoạt ảnh và audio khi rời trang','end')},
        [('q','asr','thu âm'),('q','rag','nhập chữ'),('asr','rag'),('rag','click'),('click','done','không'),('click','clean','có'),
         ('clean','key'),('key','neural','chưa có cache'),('key','bundle','cache đúng khóa'),('neural','ok'),('ok','bundle','có'),('ok','fallback','không'),
         ('fallback','result'),('result','bundle','có'),('result','device','không'),('bundle','player'),('device','player','nếu có giọng Việt'),
         ('player','audio'),('audio','rms'),('audio','subtitle'),('rms','done'),('subtitle','done')],direction='TB')
    print('Rendered 10 design figures in SVG and PNG.')


if __name__=='__main__':main()
