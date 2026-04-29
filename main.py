from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import JSONResponse
import requests
import re

app = FastAPI()

CULTURE_URL = "https://www.culture.go.kr/deduction/product/bznmk/list"


@app.get("/")
def health():
    return {"ok": True, "service": "culture-slack-bot"}


@app.post("/slack")
async def slack_command(
    background_tasks: BackgroundTasks,
    text: str = Form(""),
    response_url: str = Form("")
):
    biz_no = re.sub(r"\D", "", text)

    if not re.fullmatch(r"\d{10}", biz_no):
        return JSONResponse({
            "response_type": "ephemeral",
            "text": "사업자등록번호 10자리를 입력해주세요.\n예: `/문화비 1827700357`"
        })

    background_tasks.add_task(send_lookup_result, biz_no, response_url)

    return JSONResponse({
        "response_type": "ephemeral",
        "text": f"`{format_biz_no(biz_no)}` 조회 중입니다. 잠시만 기다려주세요."
    })


def send_lookup_result(biz_no: str, response_url: str):
    result = lookup_culture_biz(biz_no)

    text = (
        "*문화비소득공제 가맹점 조회 결과*\n"
        f"사업자등록번호: `{format_biz_no(biz_no)}`\n"
        f"등록 여부: *{result['status']}*\n"
    )

    if result.get("name"):
        text += f"상호명: {result['name']}\n"

    text += (
        "공식 조회: "
        f"https://www.culture.go.kr/deduction/product/bznmk/list?keyword={biz_no}"
    )

    requests.post(response_url, json={
        "response_type": "ephemeral",
        "text": text
    }, timeout=10)


def lookup_culture_biz(biz_no: str):
    session = requests.Session()

    base_page = "https://www.culture.go.kr/deduction/product/bznmk/list"

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "close",
        "Referer": "https://www.culture.go.kr/deduction/product/bznmk/list",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        ),
    }

    params = {
        "pageNo": "1",
        "numOfRows": "24",
        "keyword": biz_no,
        "sortType": "NEW",
    }

    try:
        # 1) 먼저 목록 페이지 접속해서 세션/쿠키 생성
        session.get(base_page, headers=headers, timeout=10)

        # 2) 실제 조회 API 호출
        r = session.get(
            base_page,
            params=params,
            headers=headers,
            timeout=15,
        )

        body = r.text
        formatted = format_biz_no(biz_no)

        if r.status_code != 200:
            return {"status": f"확인불가 / HTTP {r.status_code}"}

        if biz_no in body or formatted in body:
            name = extract_name(body)
            return {"status": "등록 Y", "name": name}

        return {"status": "등록 N"}

    except Exception as e:
        return {"status": f"확인불가 / {str(e)[:120]}"}


def extract_name(body: str):
    # 응답 구조가 정확히 확인되기 전까지는 보수적으로 처리
    for key in ["bznmkNm", "bplcNm", "storNm", "frcsNm", "name"]:
        pattern = rf'"{key}"\s*:\s*"([^"]+)"'
        match = re.search(pattern, body)
        if match:
            return match.group(1)
    return None


def format_biz_no(biz_no: str):
    return f"{biz_no[:3]}-{biz_no[3:5]}-{biz_no[5:]}"
