# MXMN DOMAIN MODEL v1.0 Candidate

## 핵심 관계

``` text
COMPANY
 ├─ USER / ROLE / PERMISSION
 ├─ CUSTOMER ── PARTNER
 ├─ WAREHOUSE
 ├─ PURCHASE / SALE / RECEIPT / PAYMENT
 ├─ IMPORT CASE
 └─ FINANCING CONTRACT

PRODUCT CATEGORY
 └─ PRODUCT ── default TAX CODE
      └─ LOT ── ESTABLISHMENT
           ├─ INBOUND / OUTBOUND
           ├─ IMPORT LOT LINK ── IMPORT CASE
           └─ FINANCING CONTRACT LOT

SERVICE ── default TAX CODE
 └─ SALE/PURCHASE ITEM

EXPENSE CODE
 └─ CHILD EXPENSE CODE (최대 4단계)
      └─ 향후 PURCHASE/SALE/EXPENSE DETAIL 참조

IMPORT CASE
 ├─ OFFER
 ├─ LC
 ├─ SHIPMENT
 │   └─ BL
 │       └─ CONTAINER
 ├─ DOCUMENT
 └─ IMPORT COST

PURCHASE
 ├─ PURCHASE ITEM
 ├─ PAYABLE
 └─ PAYMENT ALLOCATION

SALE
 ├─ SALE ITEM
 ├─ RECEIVABLE
 └─ RECEIPT ALLOCATION

FINANCING CONTRACT
 ├─ CONTRACT TERM
 ├─ CONTRACT LOT
 └─ RELEASE
     ├─ RELEASE ITEM
     └─ RELEASE CALCULATION
         └─ OUTBOUND / SALE

LOT + INBOUND/OUTBOUND
 └─ MEATWATCH TX
     └─ MEATWATCH BATCH
```

## 핵심 Business Rule

1.  Multi-Company
2.  Mixed Tax
3.  Product + Service
4.  Transaction Tax Snapshot
5.  Partner ≠ Customer Code
6.  Product ≠ LOT
7.  LOT Individual Cost
8.  One Fact → One Data
9.  Transaction Based Inventory
10. BL + Trace No. 자동 승계
11. Import Case 중심 수입관리
12. Variable Import Cost
13. Financing = 일반유통 위 추가 Layer
14. Contract Term History
15. Calculation Snapshot
16. Receipt/Payment Allocation
17. MeatWatch Integration 분리
18. Document Storage 분리
19. One Data → Multiple Reports
20. Vertical Slice Development
21. ExpenseCode는 ProductCategory와 분리된 계층형 Master
22. ExpenseCode의 최상위 손익·자동계산 항목은 시스템 표준구조
23. 거래 Detail은 ExpenseCode의 실제입력(INPUT) 말단만 참조
