"""
测试 PackageDefinition 数据类

验证字段验证逻辑和基本功能
"""

from package_library import PackageDefinition


def test_valid_package_definition():
    """测试有效的封装定义"""
    print("测试 1: 创建有效的 QFP-48 封装定义...")
    qfp48 = PackageDefinition(
        id="qfp-48-generic",
        type="QFP-48",
        pad_count=48,
        width=(6.8, 7.2),
        height=(6.8, 7.2),
        aspect_ratio=(0.95, 1.05),
        pad_pitch=0.5,
        layout_pattern="quad",
        category="IC",
        hierarchy=["IC", "QFP", "QFP-48"]
    )
    print(f"  ✓ 成功创建: {qfp48}")
    assert qfp48.id == "qfp-48-generic"
    assert qfp48.type == "QFP-48"
    assert qfp48.pad_count == 48
    assert qfp48.matches_pad_count(48)
    assert qfp48.is_in_width_range(7.0)
    assert qfp48.is_in_height_range(7.0)
    assert qfp48.is_in_aspect_ratio_range(1.0)
    print("  ✓ 所有断言通过")


def test_minimal_package_definition():
    """测试最小化封装定义（仅必填字段）"""
    print("\n测试 2: 创建最小化封装定义（仅必填字段）...")
    resistor = PackageDefinition(
        id="resistor-0603",
        type="Resistor 0603",
        pad_count=2,
        width=(1.4, 1.8),
        height=(0.7, 0.9),
        aspect_ratio=(1.8, 2.5)
    )
    print(f"  ✓ 成功创建: {resistor}")
    assert resistor.pad_pitch is None
    assert resistor.pad_shape is None
    assert resistor.category is None
    print("  ✓ 可选字段为 None")


def test_invalid_id():
    """测试无效的 id"""
    print("\n测试 3: 验证空 id 会抛出异常...")
    try:
        PackageDefinition(
            id="",
            type="Test",
            pad_count=2,
            width=(1.0, 2.0),
            height=(1.0, 2.0),
            aspect_ratio=(1.0, 2.0)
        )
        print("  ✗ 应该抛出 ValueError")
        assert False
    except ValueError as e:
        print(f"  ✓ 正确抛出异常: {e}")


def test_invalid_pad_count():
    """测试无效的 pad_count"""
    print("\n测试 4: 验证负数 pad_count 会抛出异常...")
    try:
        PackageDefinition(
            id="test",
            type="Test",
            pad_count=-1,
            width=(1.0, 2.0),
            height=(1.0, 2.0),
            aspect_ratio=(1.0, 2.0)
        )
        print("  ✗ 应该抛出 ValueError")
        assert False
    except ValueError as e:
        print(f"  ✓ 正确抛出异常: {e}")


def test_invalid_range():
    """测试无效的范围（min > max）"""
    print("\n测试 5: 验证 min > max 会抛出异常...")
    try:
        PackageDefinition(
            id="test",
            type="Test",
            pad_count=2,
            width=(2.0, 1.0),  # min > max
            height=(1.0, 2.0),
            aspect_ratio=(1.0, 2.0)
        )
        print("  ✗ 应该抛出 ValueError")
        assert False
    except ValueError as e:
        print(f"  ✓ 正确抛出异常: {e}")


def test_invalid_pad_shape():
    """测试无效的 pad_shape"""
    print("\n测试 6: 验证无效的 pad_shape 会抛出异常...")
    try:
        PackageDefinition(
            id="test",
            type="Test",
            pad_count=2,
            width=(1.0, 2.0),
            height=(1.0, 2.0),
            aspect_ratio=(1.0, 2.0),
            pad_shape="invalid"
        )
        print("  ✗ 应该抛出 ValueError")
        assert False
    except ValueError as e:
        print(f"  ✓ 正确抛出异常: {e}")


def test_invalid_layout_pattern():
    """测试无效的 layout_pattern"""
    print("\n测试 7: 验证无效的 layout_pattern 会抛出异常...")
    try:
        PackageDefinition(
            id="test",
            type="Test",
            pad_count=2,
            width=(1.0, 2.0),
            height=(1.0, 2.0),
            aspect_ratio=(1.0, 2.0),
            layout_pattern="invalid"
        )
        print("  ✗ 应该抛出 ValueError")
        assert False
    except ValueError as e:
        print(f"  ✓ 正确抛出异常: {e}")


def test_valid_pad_shapes():
    """测试所有有效的 pad_shape 值"""
    print("\n测试 8: 验证所有有效的 pad_shape 值...")
    for shape in ["circle", "rect", "oval"]:
        pkg = PackageDefinition(
            id=f"test-{shape}",
            type="Test",
            pad_count=2,
            width=(1.0, 2.0),
            height=(1.0, 2.0),
            aspect_ratio=(1.0, 2.0),
            pad_shape=shape
        )
        print(f"  ✓ {shape} 有效")


def test_valid_layout_patterns():
    """测试所有有效的 layout_pattern 值"""
    print("\n测试 9: 验证所有有效的 layout_pattern 值...")
    for pattern in ["quad", "dual", "grid"]:
        pkg = PackageDefinition(
            id=f"test-{pattern}",
            type="Test",
            pad_count=2,
            width=(1.0, 2.0),
            height=(1.0, 2.0),
            aspect_ratio=(1.0, 2.0),
            layout_pattern=pattern
        )
        print(f"  ✓ {pattern} 有效")


def test_optional_ranges():
    """测试可选范围字段的验证"""
    print("\n测试 10: 验证可选范围字段...")
    pkg = PackageDefinition(
        id="test",
        type="Test",
        pad_count=2,
        width=(1.0, 2.0),
        height=(1.0, 2.0),
        aspect_ratio=(1.0, 2.0),
        pad_width=(0.5, 1.0),
        pad_height=(0.3, 0.8)
    )
    print(f"  ✓ 成功创建带可选范围的封装: {pkg}")
    
    print("\n测试 11: 验证可选范围字段的 min > max 检查...")
    try:
        PackageDefinition(
            id="test",
            type="Test",
            pad_count=2,
            width=(1.0, 2.0),
            height=(1.0, 2.0),
            aspect_ratio=(1.0, 2.0),
            pad_width=(1.0, 0.5)  # min > max
        )
        print("  ✗ 应该抛出 ValueError")
        assert False
    except ValueError as e:
        print(f"  ✓ 正确抛出异常: {e}")


def test_hierarchy_validation():
    """测试 hierarchy 字段验证"""
    print("\n测试 12: 验证有效的 hierarchy...")
    pkg = PackageDefinition(
        id="test",
        type="Test",
        pad_count=2,
        width=(1.0, 2.0),
        height=(1.0, 2.0),
        aspect_ratio=(1.0, 2.0),
        hierarchy=["IC", "QFP", "QFP-48"]
    )
    print(f"  ✓ 成功创建带 hierarchy 的封装")
    
    print("\n测试 13: 验证无效的 hierarchy（非列表）...")
    try:
        PackageDefinition(
            id="test",
            type="Test",
            pad_count=2,
            width=(1.0, 2.0),
            height=(1.0, 2.0),
            aspect_ratio=(1.0, 2.0),
            hierarchy="not a list"
        )
        print("  ✗ 应该抛出 ValueError")
        assert False
    except ValueError as e:
        print(f"  ✓ 正确抛出异常: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("PackageDefinition 数据类测试")
    print("=" * 60)
    
    test_valid_package_definition()
    test_minimal_package_definition()
    test_invalid_id()
    test_invalid_pad_count()
    test_invalid_range()
    test_invalid_pad_shape()
    test_invalid_layout_pattern()
    test_valid_pad_shapes()
    test_valid_layout_patterns()
    test_optional_ranges()
    test_hierarchy_validation()
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过！")
    print("=" * 60)
