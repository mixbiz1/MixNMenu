"""MXMN 표준 손익·경비코드 트리 정의.

key/parent_key는 초기화 과정에서만 사용하는 안정적인 식별자이며 실제 거래에는
tb_expense_code.expense_id를 FK로 사용한다.
"""

STANDARD_EXPENSE_TREE = [
    # 매출
    ("sales", None, "매출", "SALES", "GROUP", None, 10, "상품·용역 매출 분류"),
    ("product_sales", "sales", "상품매출", "SALES", "GROUP", None, 10, None),
    ("tax_free_sales", "product_sales", "면세상품매출", "SALES", "INPUT", None, 10, None),
    ("taxable_sales", "product_sales", "과세상품매출", "SALES", "INPUT", None, 20, None),
    ("service_sales", "sales", "용역매출", "SALES", "GROUP", None, 20, None),
    ("brokerage_income", "service_sales", "중개수수료", "SALES", "INPUT", None, 10, None),
    ("logistics_income", "service_sales", "물류관리수수료", "SALES", "INPUT", None, 20, None),
    ("consulting_income", "service_sales", "컨설팅수입", "SALES", "INPUT", None, 30, None),
    ("rental_income", "service_sales", "임대수입", "SALES", "INPUT", None, 40, None),
    # 매출원가
    ("cost_of_sales", None, "매출원가", "COST_OF_SALES", "GROUP", None, 20, "상품 매입 및 매출원가 분류"),
    ("product_purchase", "cost_of_sales", "상품매입", "COST_OF_SALES", "GROUP", None, 10, None),
    ("tax_free_purchase", "product_purchase", "면세상품매입", "COST_OF_SALES", "INPUT", None, 10, None),
    ("taxable_purchase", "product_purchase", "과세상품매입", "COST_OF_SALES", "INPUT", None, 20, None),
    ("import_cost", "cost_of_sales", "수입부대원가", "COST_OF_SALES", "INPUT", None, 20, None),
    ("handling_cost", "cost_of_sales", "입출고비", "COST_OF_SALES", "INPUT", None, 30, None),
    ("warehouse_cost", "cost_of_sales", "원가반영 창고료", "COST_OF_SALES", "INPUT", None, 40, None),
    # 계산 항목과 판매관리비
    ("gross_profit", None, "매출총이익", "GROSS_PROFIT", "CALCULATED", "GROSS_PROFIT", 30, "매출 - 매출원가"),
    ("sga", None, "판매비와관리비", "SGA", "GROUP", None, 40, "영업활동에 필요한 판매·관리 비용"),
    ("labor", "sga", "인건비", "SGA", "GROUP", None, 10, None),
    ("salary", "labor", "급여", "SGA", "INPUT", None, 10, None),
    ("bonus", "labor", "상여", "SGA", "INPUT", None, 20, None),
    ("retirement", "labor", "퇴직급여", "SGA", "INPUT", None, 30, None),
    ("welfare", "sga", "복리후생비", "SGA", "INPUT", None, 20, None),
    ("freight", "sga", "운반비", "SGA", "INPUT", None, 30, None),
    ("commission", "sga", "지급수수료", "SGA", "INPUT", None, 40, None),
    ("rent", "sga", "임차료", "SGA", "INPUT", None, 50, None),
    ("vehicle", "sga", "차량유지비", "SGA", "INPUT", None, 60, None),
    ("communication", "sga", "통신비", "SGA", "INPUT", None, 70, None),
    ("taxes", "sga", "세금과공과", "SGA", "INPUT", None, 80, None),
    ("depreciation", "sga", "감가상각비", "SGA", "INPUT", None, 90, None),
    ("operating_profit", None, "영업이익", "OPERATING_PROFIT", "CALCULATED", "OPERATING_PROFIT", 50, "매출총이익 - 판매비와관리비"),
    # 영업외손익
    ("non_op_income", None, "영업외수익", "NON_OPERATING_INCOME", "GROUP", None, 60, None),
    ("interest_income", "non_op_income", "이자수익", "NON_OPERATING_INCOME", "INPUT", None, 10, None),
    ("fx_gain", "non_op_income", "외환차익", "NON_OPERATING_INCOME", "INPUT", None, 20, None),
    ("other_income", "non_op_income", "잡이익", "NON_OPERATING_INCOME", "INPUT", None, 30, None),
    ("non_op_expense", None, "영업외비용", "NON_OPERATING_EXPENSE", "GROUP", None, 70, None),
    ("interest_expense", "non_op_expense", "이자비용", "NON_OPERATING_EXPENSE", "INPUT", None, 10, None),
    ("fx_loss", "non_op_expense", "외환차손", "NON_OPERATING_EXPENSE", "INPUT", None, 20, None),
    ("other_expense", "non_op_expense", "잡손실", "NON_OPERATING_EXPENSE", "INPUT", None, 30, None),
    # 세전·세후 손익
    ("pretax_profit", None, "법인세비용차감전순이익", "PRETAX_PROFIT", "CALCULATED", "PRETAX_PROFIT", 80, "영업이익 + 영업외수익 - 영업외비용"),
    ("income_tax", None, "법인세비용(예상)", "INCOME_TAX", "CALCULATED", "ESTIMATED_INCOME_TAX", 90, "세율 설정에 따른 예상 법인세"),
    ("net_profit", None, "당기순이익(예상)", "NET_PROFIT", "CALCULATED", "NET_PROFIT", 100, "세전이익 - 예상 법인세비용"),
]

