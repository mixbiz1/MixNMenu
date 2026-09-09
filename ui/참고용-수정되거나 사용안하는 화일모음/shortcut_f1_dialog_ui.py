# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'shortcut_f1_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_ShortcutF1Dialog(object):
    def setupUi(self, ShortcutF1Dialog):
        if not ShortcutF1Dialog.objectName():
            ShortcutF1Dialog.setObjectName(u"ShortcutF1Dialog")
        ShortcutF1Dialog.resize(1000, 600)
        ShortcutF1Dialog.setStyleSheet(u"\n"
"    QDialog#ShortcutF1Dialog {\n"
"        background-color: #B0B0B0;\n"
"    }\n"
"    QLabel {\n"
"        font-family: \"Gulim\", \"Dotum\", \"Malgun Gothic\";\n"
"        font-size: 12px;\n"
"        font-weight: bold;\n"
"        color: #000080;\n"
"    }\n"
"    QPushButton {\n"
"        background-color: #FFFFFF;\n"
"        border-top: 2px solid #FFFFFF;\n"
"        border-left: 2px solid #FFFFFF;\n"
"        border-right: 2px solid #808080;\n"
"        border-bottom: 2px solid #808080;\n"
"        font-family: \"Gulim\", \"Dotum\";\n"
"        font-size: 12px;\n"
"        font-weight: bold;\n"
"        color: #000000;\n"
"        min-height: 25px;\n"
"    }\n"
"    QPushButton:pressed {\n"
"        border-top: 2px solid #808080;\n"
"        border-left: 2px solid #808080;\n"
"        border-right: 2px solid #FFFFFF;\n"
"        border-bottom: 2px solid #FFFFFF;\n"
"    }\n"
"   ")
        self.mainLayout = QVBoxLayout(ShortcutF1Dialog)
        self.mainLayout.setSpacing(10)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(10, 10, 10, 10)
        self.lay_top_info = QHBoxLayout()
        self.lay_top_info.setSpacing(10)
        self.lay_top_info.setObjectName(u"lay_top_info")
        self.lbl_company_info = QLabel(ShortcutF1Dialog)
        self.lbl_company_info.setObjectName(u"lbl_company_info")
        self.lbl_company_info.setMinimumSize(QSize(220, 26))
        self.lbl_company_info.setStyleSheet(u"background-color: #D4D0C8; border-top: 2px solid #808080; border-left: 2px solid #808080; border-right: 2px solid #FFFFFF; border-bottom: 2px solid #FFFFFF; color: #000080; font-size: 12px;")
        self.lbl_company_info.setAlignment(Qt.AlignCenter)

        self.lay_top_info.addWidget(self.lbl_company_info)

        self.lbl_expire_info = QLabel(ShortcutF1Dialog)
        self.lbl_expire_info.setObjectName(u"lbl_expire_info")
        self.lbl_expire_info.setMinimumSize(QSize(320, 26))
        self.lbl_expire_info.setStyleSheet(u"background-color: #D4D0C8; border-top: 2px solid #808080; border-left: 2px solid #808080; border-right: 2px solid #FFFFFF; border-bottom: 2px solid #FFFFFF; color: #000080; font-size: 12px;")
        self.lbl_expire_info.setAlignment(Qt.AlignCenter)

        self.lay_top_info.addWidget(self.lbl_expire_info)

        self.spacer_top = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.lay_top_info.addItem(self.spacer_top)


        self.mainLayout.addLayout(self.lay_top_info)

        self.lay_columns = QHBoxLayout()
        self.lay_columns.setSpacing(15)
        self.lay_columns.setObjectName(u"lay_columns")
        self.col_1 = QVBoxLayout()
        self.col_1.setSpacing(4)
        self.col_1.setObjectName(u"col_1")
        self.lbl_cat_code = QLabel(ShortcutF1Dialog)
        self.lbl_cat_code.setObjectName(u"lbl_cat_code")
        self.lbl_cat_code.setAlignment(Qt.AlignCenter)

        self.col_1.addWidget(self.lbl_cat_code)

        self.btn_code_common = QPushButton(ShortcutF1Dialog)
        self.btn_code_common.setObjectName(u"btn_code_common")

        self.col_1.addWidget(self.btn_code_common)

        self.btn_code_goods = QPushButton(ShortcutF1Dialog)
        self.btn_code_goods.setObjectName(u"btn_code_goods")

        self.col_1.addWidget(self.btn_code_goods)

        self.btn_cust_entry = QPushButton(ShortcutF1Dialog)
        self.btn_cust_entry.setObjectName(u"btn_cust_entry")

        self.col_1.addWidget(self.btn_cust_entry)

        self.btn_goods_entry = QPushButton(ShortcutF1Dialog)
        self.btn_goods_entry.setObjectName(u"btn_goods_entry")

        self.col_1.addWidget(self.btn_goods_entry)

        self.btn_exp_code = QPushButton(ShortcutF1Dialog)
        self.btn_exp_code.setObjectName(u"btn_exp_code")

        self.col_1.addWidget(self.btn_exp_code)

        self.sp_col1_1 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_1.addItem(self.sp_col1_1)

        self.lbl_cat_basic = QLabel(ShortcutF1Dialog)
        self.lbl_cat_basic.setObjectName(u"lbl_cat_basic")
        self.lbl_cat_basic.setAlignment(Qt.AlignCenter)

        self.col_1.addWidget(self.lbl_cat_basic)

        self.btn_basic_bal = QPushButton(ShortcutF1Dialog)
        self.btn_basic_bal.setObjectName(u"btn_basic_bal")

        self.col_1.addWidget(self.btn_basic_bal)

        self.sp_col1_2 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_1.addItem(self.sp_col1_2)

        self.lbl_cat_margin = QLabel(ShortcutF1Dialog)
        self.lbl_cat_margin.setObjectName(u"lbl_cat_margin")
        self.lbl_cat_margin.setAlignment(Qt.AlignCenter)

        self.col_1.addWidget(self.lbl_cat_margin)

        self.btn_margin_calc = QPushButton(ShortcutF1Dialog)
        self.btn_margin_calc.setObjectName(u"btn_margin_calc")

        self.col_1.addWidget(self.btn_margin_calc)

        self.sp_col1_3 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_1.addItem(self.sp_col1_3)

        self.lbl_cat_exp = QLabel(ShortcutF1Dialog)
        self.lbl_cat_exp.setObjectName(u"lbl_cat_exp")
        self.lbl_cat_exp.setAlignment(Qt.AlignCenter)

        self.col_1.addWidget(self.lbl_cat_exp)

        self.btn_exp_in = QPushButton(ShortcutF1Dialog)
        self.btn_exp_in.setObjectName(u"btn_exp_in")

        self.col_1.addWidget(self.btn_exp_in)

        self.btn_exp_out = QPushButton(ShortcutF1Dialog)
        self.btn_exp_out.setObjectName(u"btn_exp_out")

        self.col_1.addWidget(self.btn_exp_out)

        self.sp_col1_end = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_1.addItem(self.sp_col1_end)


        self.lay_columns.addLayout(self.col_1)

        self.col_2 = QVBoxLayout()
        self.col_2.setSpacing(4)
        self.col_2.setObjectName(u"col_2")
        self.lbl_cat_slip = QLabel(ShortcutF1Dialog)
        self.lbl_cat_slip.setObjectName(u"lbl_cat_slip")
        self.lbl_cat_slip.setAlignment(Qt.AlignCenter)

        self.col_2.addWidget(self.lbl_cat_slip)

        self.btn_in_slip = QPushButton(ShortcutF1Dialog)
        self.btn_in_slip.setObjectName(u"btn_in_slip")

        self.col_2.addWidget(self.btn_in_slip)

        self.btn_out_slip = QPushButton(ShortcutF1Dialog)
        self.btn_out_slip.setObjectName(u"btn_out_slip")

        self.col_2.addWidget(self.btn_out_slip)

        self.btn_pay_in = QPushButton(ShortcutF1Dialog)
        self.btn_pay_in.setObjectName(u"btn_pay_in")

        self.col_2.addWidget(self.btn_pay_in)

        self.btn_pay_out = QPushButton(ShortcutF1Dialog)
        self.btn_pay_out.setObjectName(u"btn_pay_out")

        self.col_2.addWidget(self.btn_pay_out)

        self.sp_col2_1 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_2.addItem(self.sp_col2_1)

        self.lbl_cat_meatwatch = QLabel(ShortcutF1Dialog)
        self.lbl_cat_meatwatch.setObjectName(u"lbl_cat_meatwatch")
        self.lbl_cat_meatwatch.setAlignment(Qt.AlignCenter)

        self.col_2.addWidget(self.lbl_cat_meatwatch)

        self.btn_mw_importer = QPushButton(ShortcutF1Dialog)
        self.btn_mw_importer.setObjectName(u"btn_mw_importer")

        self.col_2.addWidget(self.btn_mw_importer)

        self.btn_mw_seller = QPushButton(ShortcutF1Dialog)
        self.btn_mw_seller.setObjectName(u"btn_mw_seller")

        self.col_2.addWidget(self.btn_mw_seller)

        self.btn_mw_packer = QPushButton(ShortcutF1Dialog)
        self.btn_mw_packer.setObjectName(u"btn_mw_packer")

        self.col_2.addWidget(self.btn_mw_packer)

        self.sp_col2_2 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_2.addItem(self.sp_col2_2)

        self.btn_domestic_beef = QPushButton(ShortcutF1Dialog)
        self.btn_domestic_beef.setObjectName(u"btn_domestic_beef")

        self.col_2.addWidget(self.btn_domestic_beef)

        self.btn_domestic_pork = QPushButton(ShortcutF1Dialog)
        self.btn_domestic_pork.setObjectName(u"btn_domestic_pork")

        self.col_2.addWidget(self.btn_domestic_pork)

        self.sp_col2_end = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_2.addItem(self.sp_col2_end)


        self.lay_columns.addLayout(self.col_2)

        self.col_3 = QVBoxLayout()
        self.col_3.setSpacing(4)
        self.col_3.setObjectName(u"col_3")
        self.lbl_cat_trans = QLabel(ShortcutF1Dialog)
        self.lbl_cat_trans.setObjectName(u"lbl_cat_trans")
        self.lbl_cat_trans.setAlignment(Qt.AlignCenter)

        self.col_3.addWidget(self.lbl_cat_trans)

        self.btn_daily_total = QPushButton(ShortcutF1Dialog)
        self.btn_daily_total.setObjectName(u"btn_daily_total")

        self.col_3.addWidget(self.btn_daily_total)

        self.btn_cust_ledger = QPushButton(ShortcutF1Dialog)
        self.btn_cust_ledger.setObjectName(u"btn_cust_ledger")

        self.col_3.addWidget(self.btn_cust_ledger)

        self.btn_unpaid_stat = QPushButton(ShortcutF1Dialog)
        self.btn_unpaid_stat.setObjectName(u"btn_unpaid_stat")

        self.col_3.addWidget(self.btn_unpaid_stat)

        self.btn_stock_stat = QPushButton(ShortcutF1Dialog)
        self.btn_stock_stat.setObjectName(u"btn_stock_stat")

        self.col_3.addWidget(self.btn_stock_stat)

        self.btn_accounting_daily = QPushButton(ShortcutF1Dialog)
        self.btn_accounting_daily.setObjectName(u"btn_accounting_daily")

        self.col_3.addWidget(self.btn_accounting_daily)

        self.sp_col3_1 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_3.addItem(self.sp_col3_1)

        self.lbl_cat_history_form = QLabel(ShortcutF1Dialog)
        self.lbl_cat_history_form.setObjectName(u"lbl_cat_history_form")
        self.lbl_cat_history_form.setAlignment(Qt.AlignCenter)

        self.col_3.addWidget(self.lbl_cat_history_form)

        self.btn_trans_detail = QPushButton(ShortcutF1Dialog)
        self.btn_trans_detail.setObjectName(u"btn_trans_detail")

        self.col_3.addWidget(self.btn_trans_detail)

        self.btn_sales_ship_stat = QPushButton(ShortcutF1Dialog)
        self.btn_sales_ship_stat.setObjectName(u"btn_sales_ship_stat")

        self.col_3.addWidget(self.btn_sales_ship_stat)

        self.btn_pack_stat = QPushButton(ShortcutF1Dialog)
        self.btn_pack_stat.setObjectName(u"btn_pack_stat")

        self.col_3.addWidget(self.btn_pack_stat)

        self.btn_bundle_no_detail = QPushButton(ShortcutF1Dialog)
        self.btn_bundle_no_detail.setObjectName(u"btn_bundle_no_detail")

        self.col_3.addWidget(self.btn_bundle_no_detail)

        self.sp_col3_end = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_3.addItem(self.sp_col3_end)


        self.lay_columns.addLayout(self.col_3)

        self.col_4 = QVBoxLayout()
        self.col_4.setSpacing(4)
        self.col_4.setObjectName(u"col_4")
        self.lbl_cat_tax = QLabel(ShortcutF1Dialog)
        self.lbl_cat_tax.setObjectName(u"lbl_cat_tax")
        self.lbl_cat_tax.setAlignment(Qt.AlignCenter)

        self.col_4.addWidget(self.lbl_cat_tax)

        self.btn_buy_tax_entry = QPushButton(ShortcutF1Dialog)
        self.btn_buy_tax_entry.setObjectName(u"btn_buy_tax_entry")

        self.col_4.addWidget(self.btn_buy_tax_entry)

        self.btn_sale_tax_entry = QPushButton(ShortcutF1Dialog)
        self.btn_sale_tax_entry.setObjectName(u"btn_sale_tax_entry")

        self.col_4.addWidget(self.btn_sale_tax_entry)

        self.btn_tax_detail = QPushButton(ShortcutF1Dialog)
        self.btn_tax_detail.setObjectName(u"btn_tax_detail")

        self.col_4.addWidget(self.btn_tax_detail)

        self.btn_etax_send = QPushButton(ShortcutF1Dialog)
        self.btn_etax_send.setObjectName(u"btn_etax_send")

        self.col_4.addWidget(self.btn_etax_send)

        self.sp_col4_end = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_4.addItem(self.sp_col4_end)


        self.lay_columns.addLayout(self.col_4)

        self.col_5 = QVBoxLayout()
        self.col_5.setSpacing(4)
        self.col_5.setObjectName(u"col_5")
        self.frame_extra_service = QFrame(ShortcutF1Dialog)
        self.frame_extra_service.setObjectName(u"frame_extra_service")
        self.frame_extra_service.setStyleSheet(u"QFrame#frame_extra_service { border: 2px solid #0000FF; background-color: transparent; }")
        self.lay_extra = QVBoxLayout(self.frame_extra_service)
        self.lay_extra.setSpacing(4)
        self.lay_extra.setObjectName(u"lay_extra")
        self.lay_extra.setContentsMargins(6, 6, 6, 6)
        self.lbl_cat_extra = QLabel(self.frame_extra_service)
        self.lbl_cat_extra.setObjectName(u"lbl_cat_extra")
        self.lbl_cat_extra.setAlignment(Qt.AlignCenter)

        self.lay_extra.addWidget(self.lbl_cat_extra)

        self.btn_sms = QPushButton(self.frame_extra_service)
        self.btn_sms.setObjectName(u"btn_sms")

        self.lay_extra.addWidget(self.btn_sms)

        self.btn_fax = QPushButton(self.frame_extra_service)
        self.btn_fax.setObjectName(u"btn_fax")

        self.lay_extra.addWidget(self.btn_fax)

        self.btn_hometax = QPushButton(self.frame_extra_service)
        self.btn_hometax.setObjectName(u"btn_hometax")

        self.lay_extra.addWidget(self.btn_hometax)

        self.btn_popbill = QPushButton(self.frame_extra_service)
        self.btn_popbill.setObjectName(u"btn_popbill")

        self.lay_extra.addWidget(self.btn_popbill)


        self.col_5.addWidget(self.frame_extra_service)

        self.sp_col5_1 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_5.addItem(self.sp_col5_1)

        self.btn_remote = QPushButton(ShortcutF1Dialog)
        self.btn_remote.setObjectName(u"btn_remote")
        self.btn_remote.setStyleSheet(u"background-color: #FFFFE0; color: #FF0000; border: 1px solid #D3D3D3;")

        self.col_5.addWidget(self.btn_remote)

        self.btn_faq = QPushButton(ShortcutF1Dialog)
        self.btn_faq.setObjectName(u"btn_faq")
        self.btn_faq.setStyleSheet(u"background-color: #FFFFE0; color: #FF0000; border: 1px solid #D3D3D3;")

        self.col_5.addWidget(self.btn_faq)

        self.btn_manual = QPushButton(ShortcutF1Dialog)
        self.btn_manual.setObjectName(u"btn_manual")
        self.btn_manual.setStyleSheet(u"background-color: #FFFFE0; color: #FF0000; border: 1px solid #D3D3D3;")

        self.col_5.addWidget(self.btn_manual)

        self.sp_col5_end = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.col_5.addItem(self.sp_col5_end)


        self.lay_columns.addLayout(self.col_5)

        self.spacer_right = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.lay_columns.addItem(self.spacer_right)


        self.mainLayout.addLayout(self.lay_columns)


        self.retranslateUi(ShortcutF1Dialog)

        QMetaObject.connectSlotsByName(ShortcutF1Dialog)
    # setupUi

    def retranslateUi(self, ShortcutF1Dialog):
        ShortcutF1Dialog.setWindowTitle(QCoreApplication.translate("ShortcutF1Dialog", u"\ub2e8\ucd95\uba54\ub274 (F1)", None))
        self.lbl_company_info.setText(QCoreApplication.translate("ShortcutF1Dialog", u"(\uc8fc)\ubbf9\uc2a4\ube44\uc988  0505-810-1001", None))
        self.lbl_expire_info.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc0ac\uc6a9\uae30\ud55c : \ubb34\uc81c\ud55c (\uc601\uad6c \ub77c\uc774\uc120\uc2a4) [\ub0a8\uc740\uc77c\uc218 : \ubb34\uc81c\ud55c]", None))
        self.lbl_cat_code.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \ucf54\ub4dc\uad00\ub9ac >>", None))
        self.btn_code_common.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uacf5\ud1b5\ucf54\ub4dc\uc785\ub825(\uacf5\ud1b5)", None))
        self.btn_code_goods.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uacf5\ud1b5\ucf54\ub4dc\uc785\ub825(\uc0c1\ud488)", None))
        self.btn_cust_entry.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uac70\ub798\ucc98\uc785\ub825", None))
        self.btn_goods_entry.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc0c1\ud488\uc785\ub825", None))
        self.btn_exp_code.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uacbd\ube44\ucf54\ub4dc\uc785\ub825", None))
        self.lbl_cat_basic.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \uae30\ucd08\ub4f1\ub85d >>", None))
        self.btn_basic_bal.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uae30\ucd08\uc794\uc561\uc785\ub825", None))
        self.lbl_cat_margin.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \ub9e4\ucd9c\uc774\uc775\uc815\uc0b0 >>", None))
        self.btn_margin_calc.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ub9e4\ucd9c\uc774\uc775\uc815\uc0b0", None))
        self.lbl_cat_exp.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \uacbd\ube44\uc804\ud45c\uad00\ub9ac >>", None))
        self.btn_exp_in.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc785\uae08(\uacbd\ube44)\uc785\ub825", None))
        self.btn_exp_out.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ucd9c\uae08(\uacbd\ube44)\uc785\ub825", None))
        self.lbl_cat_slip.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \uc804\ud45c\uad00\ub9ac >>", None))
        self.btn_in_slip.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc785\uace0\uc804\ud45c(\uc785\ub825/\uc218\uc815)", None))
        self.btn_out_slip.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ucd9c\uace0\uc804\ud45c(\uc785\ub825/\uc218\uc815)", None))
        self.btn_pay_in.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc785\uae08\uc804\ud45c(\uc785\ub825/\uc218\uc815)", None))
        self.btn_pay_out.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ucd9c\uae08\uc804\ud45c(\uc785\ub825/\uc218\uc815)", None))
        self.lbl_cat_meatwatch.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \uc720\ud1b5\uc774\ub825\uc2e0\uace0\ud30c\uc77c >>", None))
        self.btn_mw_importer.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ubbf8\ud2b8\uc640\uce58 \uc218\uc785\uc5c5\uc790", None))
        self.btn_mw_seller.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ubbf8\ud2b8\uc640\uce58 \ud310\ub9e4\uc5c5\uc790", None))
        self.btn_mw_packer.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ubbf8\ud2b8\uc640\uce58 \ud3ec\uc7a5\ucc98\ub9ac", None))
        self.btn_domestic_beef.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uad6d\ub0b4\uc0b0\uc1e0\uace0\uae30", None))
        self.btn_domestic_pork.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uad6d\ub0b4\uc0b0\ub3fc\uc9c0\uace0\uae30", None))
        self.lbl_cat_trans.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \uac70\ub798\ub0b4\uc5ed\uad00\ub9ac >>", None))
        self.btn_daily_total.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc77c \uacc4 \ud45c", None))
        self.btn_cust_ledger.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uac70\ub798\ucc98\uc6d0\uc7a5", None))
        self.btn_unpaid_stat.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ubbf8\uc218/\ubbf8\uc9c0\uae09\ud604\ud669", None))
        self.btn_stock_stat.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc0c1\ud488\uc7ac\uace0\ud604\ud669", None))
        self.btn_accounting_daily.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uacbd\ub9ac\uc77c\ubcf4", None))
        self.lbl_cat_history_form.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \uc774\ub825\uad00\ub9ac\uc591\uc2dd >>", None))
        self.btn_trans_detail.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uac70\ub798\ub0b4\uc5ed\uc11c", None))
        self.btn_sales_ship_stat.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ud310\ub9e4\u00b7\ubc18\ucd9c \uc2e4\uc801", None))
        self.btn_pack_stat.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ud3ec\uc7a5\ucc98\ub9ac \uc2e4\uc801", None))
        self.btn_bundle_no_detail.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ubb36\uc74c\ubc88\ud638\uad6c\uc131\ub0b4\uc5ed\uc11c", None))
        self.lbl_cat_tax.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \uacc4\uc0b0\uc11c\uad00\ub9ac >>", None))
        self.btn_buy_tax_entry.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ub9e4\uc785\uacc4\uc0b0\uc11c\uc785\ub825", None))
        self.btn_sale_tax_entry.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ub9e4\ucd9c\uacc4\uc0b0\uc11c\uc785\ub825", None))
        self.btn_tax_detail.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uacc4\uc0b0\uc11c\ub0b4\uc5ed", None))
        self.btn_etax_send.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc804\uc790\uacc4\uc0b0\uc11c\uc804\uc1a1", None))
        self.lbl_cat_extra.setText(QCoreApplication.translate("ShortcutF1Dialog", u"<< \ubd80\uac00\uc11c\ube44\uc2a4 >>", None))
        self.btn_sms.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ubb38\uc790\ubc1c\uc1a1", None))
        self.btn_fax.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ud329\uc2a4\ubc1c\uc1a1", None))
        self.btn_hometax.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uad6d\uc138\uccad\uc790\ub8cc\uc870\ud68c", None))
        self.btn_popbill.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ud31d\ube4c", None))
        self.btn_remote.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc6d0\uaca9\uc9c0\uc6d0", None))
        self.btn_faq.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\uc790\uc8fc\ubb3b\ub294\uc9c8\ubb38", None))
        self.btn_manual.setText(QCoreApplication.translate("ShortcutF1Dialog", u"\ud504\ub85c\uadf8\ub7a8 \uc0ac\uc6a9\uc124\uba85\uc11c", None))
    # retranslateUi

