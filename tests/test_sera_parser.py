from pathlib import Path
import pandas as pd
from misharp.connectors.sera_report import parse_sera_xlsx

def test_sera_parser(tmp_path: Path):
    p = tmp_path / "SERA_report_20260813_233242.xlsx"
    pd.DataFrame([{"상품번호":29046,"상품코드":"P1","상품명":"테스트","가격":54500,"조회수":29,"조회_PC":1,"조회_Mobile":28,"주문수":1,"주문_PC":0,"주문_Mobile":1,"OpV":0.0345,"ESpV":1879,"상품상세경로":"https://x/?product_no=29046"}]).to_excel(p,index=False)
    dt, rows = parse_sera_xlsx(p)
    assert rows[0]["product_no"] == 29046
    assert rows[0]["orders"] == 1
