# core/urls.py
from django.urls import path
from . import views
from .views import prediction_select_view, coin_prediction_view

urlpatterns = [
    # Pages
    path("", views.home, name="home"),
    path("coins/", views.coin_list, name="coin_list"),
    path("coins/<str:coin_id>/", views.coin_detail, name="coin_detail"),
    path("news/", views.crypto_news, name="crypto_news"),
    path("analysis/", views.technical_analysis_page, name="technical_analysis"),
    path("analysis/<str:symbol>/", views.coin_analysis_view, name="coin_analysis"),
    path("prediction/", prediction_select_view, name="prediction_select"),
    path("prediction/<str:symbol>/", coin_prediction_view, name="coin_prediction"),
    path("onchain-dashboard/", views.onchain_dashboard, name="onchain_dashboard"),

    # APIs
    path("api/analysis/<str:coin>/", views.api_technical_analysis),
    path("api/onchain-metrics/", views.get_onchain_metrics, name="onchain_metrics"),
    path("api/sentiment/", views.get_sentiment_analysis, name="sentiment_analysis"),
    path("api/exchange-flows/", views.get_exchange_flows, name="exchange_flows"),
    path("api/complete-analysis/", views.get_complete_analysis, name="complete_analysis"),
    path("api/trading-signal/", views.get_trading_signal, name="trading_signal"),
    path("api/whale-activity/", views.get_whale_activity, name="whale_activity"),
    path("api/batch-analysis/", views.batch_analysis, name="batch_analysis"),
]

