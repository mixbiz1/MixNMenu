from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean
from sqlalchemy.sql import func
from database import Base

class Account(Base):
    """
    거래처 정보 테이블
    """
    __tablename__ = "tb_account"

    account_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_code = Column(String(20), unique=True, nullable=False, index=True) # 거래처코드
    account_name = Column(String(100), nullable=False)                        # 거래처명
    biz_no = Column(String(20), nullable=True)                                 # 사업자등록번호
    ceo_name = Column(String(50), nullable=True)                               # 대표자명
    phone = Column(String(20), nullable=True)                                  # 전화번호
    use_yn = Column(Boolean, default=True, nullable=False)                     # 사용여부
    created_at = Column(DateTime(timezone=True), server_default=func.now())   # 등록일시

class Product(Base):
    """
    품목(육류) 정보 테이블
    """
    __tablename__ = "tb_product"

    product_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_code = Column(String(30), unique=True, nullable=False, index=True) # 품목코드
    product_name = Column(String(100), nullable=False)                        # 품목명 (예: 우삼겹, 삼겹살)
    category = Column(String(50), nullable=True)                              # 카테고리 (돈육/우육 등)
    origin = Column(String(50), nullable=True)                                # 원산지 (미국/칠레/스페인 등)
    unit_price = Column(Numeric(12, 2), default=0)                            # 기본 단가
    use_yn = Column(Boolean, default=True, nullable=False)                    # 사용여부
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 등록일시