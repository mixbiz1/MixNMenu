from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

# ==========================================
# 1. 기준정보 마스터 테이블
# ==========================================

class Company(Base):
    """
    사업장/자사 정보 테이블 (멀티 사업장 및 미트워치 설정)
    """
    __tablename__ = "tb_company"

    comp_code = Column(String(10), primary_key=True, index=True) # 사업장코드 (복수 법인: 명시 입력)
    comp_name = Column(String(100), nullable=False)             # 사업자명
    comp_name_en = Column(String(100), nullable=True)           # 사업자명(영문)
    biz_no = Column(String(20), nullable=False)                  # 등록번호(사업자번호)
    ceo_name = Column(String(50), nullable=True)                 # 대표자명
    zip_code = Column(String(10), nullable=True)                 # 우편번호
    address = Column(String(200), nullable=True)                 # 주소
    uptae = Column(String(50), nullable=True)                    # 업태
    upjong = Column(String(50), nullable=True)                   # 업종
    lic_no = Column(String(50), nullable=True)                   # 영업허가번호
    bank1 = Column(String(50), nullable=True)                    # 계좌번호1
    bank2 = Column(String(50), nullable=True)                    # 계좌번호2
    tel = Column(String(30), nullable=True)                      # 전화번호
    fax = Column(String(30), nullable=True)                      # 팩스번호
    pcs = Column(String(30), nullable=True)                      # PCS 번호
    email = Column(String(100), nullable=True)                   # Email ID
    consult = Column(String(50), nullable=True)                  # 제품관련상담
    meatwatch_bplc_no = Column(String(20), nullable=True)        # 축산물이력제 사업장관리번호
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계 설정
    slips = relationship("SlipHeader", back_populates="company")


class User(Base):
    """
    사용자(로그인) 정보 테이블
    """
    __tablename__ = "tb_user"

    user_id = Column(String(50), primary_key=True, index=True) # 사용자 ID
    user_name = Column(String(50), nullable=False)             # 사용자명
    password_hash = Column(String(255), nullable=False)        # 암호화된 비밀번호 (또는 평문 비밀번호)
    use_yn = Column(Boolean, default=True, nullable=False)     # 계정 활성화 여부
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CodeGroup(Base):
    """MXMN 전 모듈에서 공유하는 공통코드 그룹."""
    __tablename__ = "tb_code_group"

    code_group_id = Column(Integer, primary_key=True, autoincrement=True)
    group_code = Column(String(30), unique=True, nullable=False, index=True)
    group_name = Column(String(100), nullable=False)
    description = Column(String(300), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    system_yn = Column(Boolean, default=False, nullable=False)
    use_yn = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    values = relationship(
        "CodeValue",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="CodeValue.sort_order, CodeValue.code",
    )


class CodeValue(Base):
    """공통코드 그룹에 속하는 실제 코드값."""
    __tablename__ = "tb_code_value"
    __table_args__ = (
        UniqueConstraint("code_group_id", "code", name="UQ_tb_code_value_group_code"),
    )

    code_value_id = Column(Integer, primary_key=True, autoincrement=True)
    code_group_id = Column(
        Integer,
        ForeignKey("tb_code_group.code_group_id"),
        nullable=False,
        index=True,
    )
    code = Column(String(30), nullable=False)
    code_name = Column(String(100), nullable=False)
    description = Column(String(300), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    extra_value1 = Column(String(200), nullable=True)
    extra_value2 = Column(String(200), nullable=True)
    use_yn = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    group = relationship("CodeGroup", back_populates="values")


class Account(Base):
    """회사 간 공유하는 실제 사업자/거래처 Master."""
    __tablename__ = "tb_account"

    account_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_code = Column(String(20), unique=True, nullable=False, index=True)
    account_name = Column(String(100), nullable=False)  # 실제 상호명
    biz_no = Column(String(20), nullable=True)
    corp_no = Column(String(20), nullable=True)
    ceo_name = Column(String(50), nullable=True)
    zip_code = Column(String(10), nullable=True)
    address = Column(String(200), nullable=True)
    address_detail = Column(String(200), nullable=True)
    uptae = Column(String(100), nullable=True)
    upjong = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    fax = Column(String(30), nullable=True)
    contact_name = Column(String(50), nullable=True)
    contact_mobile = Column(String(30), nullable=True)
    tax_email = Column(String(150), nullable=True)  # 전자(세금)계산서 이메일 1개
    bank_name = Column(String(50), nullable=True)
    bank_account_no = Column(String(80), nullable=True)
    bank_account_holder = Column(String(100), nullable=True)
    meatwatch_cust_no = Column(String(20), nullable=True)
    memo = Column(String(1000), nullable=True)
    use_yn = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    slips = relationship("SlipHeader", back_populates="account")

class Product(Base):
    """
    품목(수입육류) 정보 테이블
    """
    __tablename__ = "tb_product"

    product_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_code = Column(String(30), unique=True, nullable=False, index=True) # 품목코드
    product_name = Column(String(100), nullable=False)                        # 품목명 (예: 우삼겹, 삼겹살)
    category = Column(String(50), nullable=True)                              # 카테고리 (돈육/우육 등)
    origin = Column(String(50), nullable=True)                                # 원산지 (미국/칠레/스페인 등)
    meat_regn_code = Column(String(10), nullable=True)                        # 축산물이력제 부위코드 (예: 'BF008')
    meat_regn_name = Column(String(50), nullable=True)                        # 축산물이력제 부위명 (예: '양지')
    tax_type = Column(String(1), default='2', nullable=False)                 # 1: 과세, 2: 면세(미가공 정육)
    unit_price = Column(Numeric(12, 2), default=0)                            # 기본 단가
    use_yn = Column(Boolean, default=True, nullable=False)                    # 사용여부
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 등록일시

    # 관계 설정
    slip_details = relationship("SlipDetail", back_populates="product")


# ==========================================
# 2. 거래전표(입/출고, 파이낸싱) 트랜잭션 테이블
# ==========================================

class SlipHeader(Base):
    """
    매입/매출 전표 헤더 테이블 (과세/면세 및 축산물이력제 신고 상태 포함)
    """
    __tablename__ = "tb_slip_hdr"

    slip_no = Column(String(25), primary_key=True, index=True)                  # 전표번호 (예: 'O1-20260901-001-06')
    comp_code = Column(String(10), ForeignKey("tb_company.comp_code"), nullable=False) # 사업장코드
    slip_date = Column(String(8), nullable=False, index=True)                  # 거래일자 (YYYYMMDD)
    slip_type = Column(String(1), nullable=False)                              # 1: 매입(입고), 2: 매출(출고), 3: 파이낸싱
    account_id = Column(Integer, ForeignKey("tb_account.account_id"), nullable=False) # 거래처 FK
    tax_type = Column(String(1), default='2', nullable=False)                  # 1: 과세(세금계산서), 2: 면세(계산서)
    total_qty = Column(Integer, default=0)                                     # 총 박스 수량
    total_weight = Column(Numeric(12, 2), default=0)                           # 총 중량(KG)
    total_amount = Column(Numeric(18, 2), default=0)                           # 총 공급가액
    vat_amount = Column(Numeric(18, 2), default=0)                             # 부가가치세
    tax_bill_status = Column(String(1), default='0')                           # 0: 미발행, 1: 엑셀생성완료, 2: 홈택스발행완료
    meatwatch_yn = Column(String(1), default='N')                              # 축산물이력제 신고여부 (Y/N)
    reg_user = Column(String(50), nullable=True)                               # 작성자
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계 설정
    company = relationship("Company", back_populates="slips")
    account = relationship("Account", back_populates="slips")
    details = relationship("SlipDetail", back_populates="header", cascade="all, delete-orphan")


class SlipDetail(Base):
    """
    매입/매출 전표 상세 테이블 (유통식별번호/이력번호 관리)
    """
    __tablename__ = "tb_slip_dtl"

    slip_no = Column(String(25), ForeignKey("tb_slip_hdr.slip_no"), primary_key=True) # 전표번호 FK
    seq = Column(Integer, primary_key=True)                                          # 순번
    product_id = Column(Integer, ForeignKey("tb_product.product_id"), nullable=False) # 품목 FK
    history_no = Column(String(20), nullable=False, index=True)                       # 유통식별번호 / 이력번호 (12~15자리)
    box_qty = Column(Integer, default=0)                                              # 거래 박스 수량
    weight = Column(Numeric(12, 2), nullable=False)                                   # 거래 중량 (KG)
    unit_price = Column(Numeric(18, 2), nullable=False)                               # 단가 (원/KG)
    supply_amount = Column(Numeric(18, 2), nullable=False)                            # 공급가액
    vat = Column(Numeric(18, 2), default=0)                                           # 부세
    wh_location_no = Column(String(10), nullable=True)                               # 입출고장소(창고) 관리번호 (예: '06')

    # 관계 설정
    header = relationship("SlipHeader", back_populates="details")
    product = relationship("Product", back_populates="slip_details")

class CompanyAccount(Base):
    """업무회사별 거래처 관계 및 세무 자동화 설정."""
    __tablename__ = "tb_company_account"
    company_account_id = Column(Integer, primary_key=True, autoincrement=True)
    comp_code = Column(String(10), ForeignKey("tb_company.comp_code"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("tb_account.account_id"), nullable=False, index=True)
    trade_status = Column(String(20), default="TRADE", nullable=False)
    trade_type = Column(String(30), default="GENERAL", nullable=False)
    purchase_yn = Column(Boolean, default=False, nullable=False)
    sales_yn = Column(Boolean, default=False, nullable=False)
    tax_doc_type = Column(String(20), default="NONE", nullable=False)
    sales_tax_auto_yn = Column(Boolean, default=False, nullable=False)
    purchase_tax_manage_yn = Column(Boolean, default=False, nullable=False)
    trade_stop_yn = Column(Boolean, default=False, nullable=False)
    invoice_issue_yn = Column(Boolean, default=False, nullable=False)
    use_yn = Column(Boolean, default=True, nullable=False)
    memo = Column(String(1000), nullable=True)
