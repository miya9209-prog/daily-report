from misharp.services.sync_inventory import classify_inventory


def test_inventory_classes():
    assert classify_inventory(5, 1)[1] == "품절임박"
    assert classify_inventory(20, 1)[1] == "정상재고"
    assert classify_inventory(45, 1)[1] == "관찰재고"
    assert classify_inventory(90, 1)[1] == "과잉재고"
    assert classify_inventory(121, 1)[1] == "장기재고"
    assert classify_inventory(10, 0)[1] == "판매정체"
