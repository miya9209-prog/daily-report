from __future__ import annotations

from io import BytesIO

import pandas as pd


def dataframe_to_xlsx(df: pd.DataFrame, sheet_name: str = "data") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        worksheet = writer.sheets[sheet_name[:31]]
        worksheet.freeze_panes(1, 0)
        for i, column in enumerate(df.columns):
            width = min(max(len(str(column)) + 2, 12), 40)
            worksheet.set_column(i, i, width)
    return output.getvalue()


def multi_sheet_xlsx(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            safe = name[:31]
            df.to_excel(writer, sheet_name=safe, index=False)
            ws = writer.sheets[safe]
            ws.freeze_panes(1, 0)
            for i, column in enumerate(df.columns):
                width = min(max(len(str(column)) + 2, 12), 40)
                ws.set_column(i, i, width)
    return output.getvalue()
