# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_dashboard.ui'
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
from PySide6.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QLabel,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

class Ui_MainDashboard(object):
    def setupUi(self, MainDashboard):
        if not MainDashboard.objectName():
            MainDashboard.setObjectName(u"MainDashboard")
        MainDashboard.resize(1100, 650)
        MainDashboard.setStyleSheet(u"background-color: #EAECEE;")
        self.verticalLayout_main = QVBoxLayout(MainDashboard)
        self.verticalLayout_main.setObjectName(u"verticalLayout_main")
        self.verticalLayout_main.setContentsMargins(20, 20, 20, 20)
        self.horizontalLayout_header = QHBoxLayout()
        self.horizontalLayout_header.setObjectName(u"horizontalLayout_header")
        self.lbl_company = QLabel(MainDashboard)
        self.lbl_company.setObjectName(u"lbl_company")
        font = QFont()
        font.setFamilies([u"Malgun Gothic"])
        font.setPointSize(12)
        font.setBold(True)
        self.lbl_company.setFont(font)
        self.lbl_company.setStyleSheet(u"color: #1A237E;")

        self.horizontalLayout_header.addWidget(self.lbl_company)

        self.lbl_status = QLabel(MainDashboard)
        self.lbl_status.setObjectName(u"lbl_status")
        font1 = QFont()
        font1.setFamilies([u"Malgun Gothic"])
        font1.setPointSize(10)
        self.lbl_status.setFont(font1)
        self.lbl_status.setStyleSheet(u"color: #333333;")

        self.horizontalLayout_header.addWidget(self.lbl_status)

        self.horizontalSpacer_header = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_header.addItem(self.horizontalSpacer_header)


        self.verticalLayout_main.addLayout(self.horizontalLayout_header)

        self.gridLayout_cards = QGridLayout()
        self.gridLayout_cards.setSpacing(20)
        self.gridLayout_cards.setObjectName(u"gridLayout_cards")

        self.verticalLayout_main.addLayout(self.gridLayout_cards)

        self.verticalSpacer_bottom = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_main.addItem(self.verticalSpacer_bottom)


        self.retranslateUi(MainDashboard)

        QMetaObject.connectSlotsByName(MainDashboard)
    # setupUi

    def retranslateUi(self, MainDashboard):
        MainDashboard.setWindowTitle(QCoreApplication.translate("MainDashboard", u"\ub2e8\ucd95\uba54\ub274 \ub300\uc2dc\ubcf4\ub4dc", None))
        self.lbl_company.setText(QCoreApplication.translate("MainDashboard", u"(\uc8fc)\ubbf9\uc2a4\ube44\uc988 - MixNMenu", None))
        self.lbl_status.setText(QCoreApplication.translate("MainDashboard", u"\uc8fc\uc694 \uc5c5\ubb34\ub97c \ubc14\ud0d5\ud654\uba74 \ub2e8\ucd95\uba54\ub274\uc5d0\uc11c \ubc14\ub85c \uc2e4\ud589\ud558\uc138\uc694.", None))
    # retranslateUi

