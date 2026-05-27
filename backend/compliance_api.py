import logging
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from compliance_engine import analyze_document, record_review, ComplianceAnalysisError

app = FastAPI(
    title='Local Compliance Document Analysis Engine',
    description='Secure local compliance engine for ISO workflows, document validation, scoring and decision making.',
    version='1.0.0',
)

logger = logging.getLogger('compliance_api')


@app.get('/')
def root():
    return {'status': 'ok', 'service': 'compliance-engine'}


@app.post('/analyze')
async def analyze_document_endpoint(
    file: UploadFile = File(...),
    norm: str = Form('ISO9001'),
):
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail='Uploaded file is empty.')
        result = analyze_document(file_bytes=contents, filename=file.filename, norm=norm)
        return JSONResponse(content=result)
    except ComplianceAnalysisError as exc:
        logger.exception('Analysis error')
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception('Unexpected error during analysis')
        raise HTTPException(status_code=500, detail='Internal analysis error')


@app.post('/review')
async def review_document_endpoint(
    document_id: str = Form(...),
    decision: str = Form(...),
    corrections: str = Form('{}'),
):
    try:
        corrections_data = {}
        if corrections:
            import json
            corrections_data = json.loads(corrections)
        result = record_review(document_id=document_id, decision=decision, corrections=corrections_data)
        return JSONResponse(content=result)
    except ValueError:
        raise HTTPException(status_code=400, detail='Corrections must be valid JSON.')
    except Exception:
        raise HTTPException(status_code=500, detail='Unable to record review decision.')
