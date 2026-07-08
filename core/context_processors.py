def nav_context(request):
    url_name = ""
    if request.resolver_match:
        url_name = request.resolver_match.url_name or ""

    nav_map = {
        "home": "home",
        "coin_list": "coins",
        "coin_detail": "coins",
        "crypto_news": "news",
        "technical_analysis": "analysis",
        "coin_analysis": "analysis",
        "prediction_select": "prediction",
        "coin_prediction": "prediction",
        "onchain_dashboard": "onchain",
    }

    return {"active_nav": nav_map.get(url_name, "")}
