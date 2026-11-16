from streamlit.testing.v1 import AppTest

def test_app_renders_answer_sources_and_filters_without_exception(monkeypatch):
    calls=[]
    def fake_answer(question, **kwargs):
        calls.append(kwargs)
        return {'status':'answered','answer':'Hệ thống AI cần giám sát của con người. [S1]',
                'citations':[{'source_id':'S1','title':'Nguồn kiểm tra','excerpt':'AI requires human oversight.',
                              'source_url':'https://www.nist.gov/','location':'Article 1'}],
                'retrieval_mode':'vector'}
    monkeypatch.setattr('src.rag.answerer.answer',fake_answer)
    app=AppTest.from_file('app.py',default_timeout=30).run()
    assert not app.exception
    assert len(app.tabs)==3
    app.text_area[0].set_value('AI cần giám sát như thế nào?')
    app.button(key='qa_btn').click().run()
    assert not app.exception
    assert calls and calls[0]['top_k']>0
    assert any('Nguồn kiểm tra' in exp.label for exp in app.expander)


def test_update_button_starts_background_job_and_counts_use_active_inventory(monkeypatch):
    import streamlit as st
    from src.catalog import load_inventory
    calls=[]
    monkeypatch.setattr('src.updates.service.get_update_status',lambda:{})
    def start(**kwargs):
        calls.append(kwargs)
        return {'job_id':'test','status':'queued','progress':0,'message':'Đang kiểm tra nguồn API.'}
    monkeypatch.setattr('src.updates.service.start_update',start)
    st.cache_data.clear()
    app=AppTest.from_file('app.py',default_timeout=30).run()
    assert not app.exception
    assert app.sidebar.metric[0].label=='Đang tra cứu'
    assert int(app.sidebar.metric[0].value)==load_inventory()[2]['active']
    app.button(key='update_data_btn').click().run()
    assert not app.exception and calls==[{'max_documents':20}]
    assert len(app.get('progress'))==1


def test_upload_selection_is_sent_to_same_update_button_without_api(monkeypatch):
    import io
    import streamlit as st
    file=io.BytesIO(b'User supplied AI document. '*30);file.name='Chính sách.pdf'
    calls=[]
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:[file])
    monkeypatch.setattr('src.updates.service.get_update_status',lambda:{})
    monkeypatch.setattr('src.updates.service.start_update',lambda **kw:calls.append(kw) or {'job_id':'test-upload','status':'queued'})
    st.cache_data.clear()
    app=AppTest.from_file('app.py',default_timeout=30).run()
    app.checkbox(key='fetch_api').uncheck().run()
    app.button(key='update_data_btn').click().run()
    assert not app.exception
    assert calls[0]['providers']==[] and calls[0]['uploads'][0]['name']=='Chính sách.pdf'
    assert calls[0]['uploads'][0]['content']==file.getvalue()
