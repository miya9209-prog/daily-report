from misharp.services.recovery_engine import classify_product

def test_winner():
    d = classify_product(views=100,carts=12,orders=4,cvr=4.0,cart_rate=12.0,cart_to_order=33.3,stock=20)
    assert d.decision == "매출광고"

def test_detail_improvement():
    d = classify_product(views=100,carts=2,orders=0,cvr=0.0,cart_rate=2.0,cart_to_order=0.0,stock=5)
    assert d.decision == "상세개선"
