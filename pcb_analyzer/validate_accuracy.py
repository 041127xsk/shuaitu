#!/usr/bin/env python3
"""
孔位准确性验证脚本
通过对比 Gerber 原始数据和提取结果来验证准确性
"""

import csv
import sys
import warnings
from pathlib import Path
from gerbonara import GerberFile


def extract_flash_from_gerber(gerber_path):
    """直接从 Gerber 文件提取 Flash 对象作为参考"""
    print(f"\n从 Gerber 文件提取参考数据: {gerber_path.name}")
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        try:
            layer = GerberFile.open(str(gerber_path))
        except Exception as e:
            print(f"❌ 无法打开文件: {e}")
            return []
    
    flashes = []
    for obj in layer.objects:
        if type(obj).__name__ == 'Flash':
            flashes.append({
                'x': round(obj.x, 3),
                'y': round(obj.y, 3),
                'type': type(obj.aperture).__name__
            })
    
    print(f"  提取到 {len(flashes)} 个 Flash 对象")
    return flashes


def load_extracted_pads(csv_path):
    """加载脚本提取的焊盘数据"""
    print(f"\n加载提取结果: {csv_path}")
    
    pads = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pads.append({
                'x': round(float(row['x']), 3),
                'y': round(float(row['y']), 3),
                'shape': row['shape']
            })
    
    print(f"  加载了 {len(pads)} 个焊盘")
    return pads


def compare_coordinates(reference, extracted, tolerance=0.1):
    """对比参考数据和提取数据"""
    print(f"\n对比坐标 (容差: {tolerance}mm)")
    print("=" * 60)
    
    # 创建坐标集合用于快速查找
    ref_coords = {(p['x'], p['y']) for p in reference}
    ext_coords = {(p['x'], p['y']) for p in extracted}
    
    # 精确匹配
    exact_matches = ref_coords & ext_coords
    
    # 容差匹配
    matched = set()
    unmatched_ref = []
    unmatched_ext = []
    
    for ref_pad in reference:
        found = False
        for ext_pad in extracted:
            if (ext_pad['x'], ext_pad['y']) in matched:
                continue
            
            dx = abs(ref_pad['x'] - ext_pad['x'])
            dy = abs(ref_pad['y'] - ext_pad['y'])
            
            if dx <= tolerance and dy <= tolerance:
                matched.add((ext_pad['x'], ext_pad['y']))
                found = True
                break
        
        if not found:
            unmatched_ref.append(ref_pad)
    
    for ext_pad in extracted:
        if (ext_pad['x'], ext_pad['y']) not in matched:
            unmatched_ext.append(ext_pad)
    
    # 统计结果
    total_ref = len(reference)
    total_ext = len(extracted)
    matched_count = len(matched)
    
    print(f"参考数据 (Gerber): {total_ref} 个 Flash")
    print(f"提取数据 (CSV):   {total_ext} 个焊盘")
    print(f"匹配成功:         {matched_count} 个")
    print(f"精确匹配:         {len(exact_matches)} 个")
    
    accuracy = matched_count / total_ref * 100 if total_ref > 0 else 0
    print(f"\n准确率: {accuracy:.1f}%")
    
    # 详细报告
    if unmatched_ref:
        print(f"\n⚠️  参考数据中有 {len(unmatched_ref)} 个未匹配 (可能遗漏):")
        for i, pad in enumerate(unmatched_ref[:5]):
            print(f"  {i+1}. ({pad['x']}, {pad['y']}) - {pad['type']}")
        if len(unmatched_ref) > 5:
            print(f"  ... 还有 {len(unmatched_ref)-5} 个")
    
    if unmatched_ext:
        print(f"\n⚠️  提取数据中有 {len(unmatched_ext)} 个未匹配 (可能误提取):")
        for i, pad in enumerate(unmatched_ext[:5]):
            print(f"  {i+1}. ({pad['x']}, {pad['y']}) - {pad['shape']}")
        if len(unmatched_ext) > 5:
            print(f"  ... 还有 {len(unmatched_ext)-5} 个")
    
    return {
        'total_ref': total_ref,
        'total_ext': total_ext,
        'matched': matched_count,
        'exact_matches': len(exact_matches),
        'accuracy': accuracy,
        'unmatched_ref': unmatched_ref,
        'unmatched_ext': unmatched_ext
    }


def validate_single_file(gerber_path, csv_path):
    """验证单个 Gerber 文件"""
    print("\n" + "=" * 60)
    print(f"验证文件: {gerber_path.name}")
    print("=" * 60)
    
    reference = extract_flash_from_gerber(gerber_path)
    extracted = load_extracted_pads(csv_path)
    
    if not reference:
        print("❌ 无法从 Gerber 提取参考数据")
        return None
    
    if not extracted:
        print("❌ 无法加载提取结果")
        return None
    
    result = compare_coordinates(reference, extracted)
    
    return result


def validate_multi_layer(input_dir, csv_path):
    """验证多层 Gerber 文件"""
    print("\n" + "=" * 60)
    print("多层验证模式")
    print("=" * 60)
    
    input_dir = Path(input_dir)
    
    # 查找所有 Gerber 文件
    gerber_files = []
    for ext in ['.gbr', '.gb', '.ger']:
        gerber_files.extend(input_dir.glob(f'*{ext}'))
    
    if not gerber_files:
        print("❌ 未找到 Gerber 文件")
        return None
    
    print(f"找到 {len(gerber_files)} 个 Gerber 文件")
    
    # 从所有文件提取 Flash
    all_reference = []
    for gf in gerber_files:
        flashes = extract_flash_from_gerber(gf)
        all_reference.extend(flashes)
    
    # 去重（使用容差）
    print(f"\n合并去重...")
    unique_ref = []
    seen = set()
    tolerance = 0.05
    
    for flash in all_reference:
        key = (round(flash['x'] / tolerance), round(flash['y'] / tolerance))
        if key not in seen:
            seen.add(key)
            unique_ref.append(flash)
    
    print(f"  原始: {len(all_reference)} 个")
    print(f"  去重后: {len(unique_ref)} 个")
    
    # 加载提取结果
    extracted = load_extracted_pads(csv_path)
    
    # 对比
    result = compare_coordinates(unique_ref, extracted, tolerance=0.1)
    
    return result


def visual_spot_check(csv_path, sample_size=10):
    """随机抽样检查"""
    print("\n" + "=" * 60)
    print(f"随机抽样检查 (样本数: {sample_size})")
    print("=" * 60)
    
    import random
    
    pads = load_extracted_pads(csv_path)
    
    if len(pads) < sample_size:
        sample_size = len(pads)
    
    samples = random.sample(pads, sample_size)
    
    print("\n随机样本:")
    print(f"{'序号':<6} {'X坐标':<12} {'Y坐标':<12} {'形状':<10}")
    print("-" * 50)
    
    for i, pad in enumerate(samples, 1):
        print(f"{i:<6} {pad['x']:<12.3f} {pad['y']:<12.3f} {pad['shape']:<10}")
    
    print("\n请手动在 Gerber 查看器中验证这些坐标是否存在焊盘")
    print("推荐工具: gerbv, KiCad Gerber Viewer, ViewMate")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python validate_accuracy.py <gerber_file> <pads.csv>")
        print("  python validate_accuracy.py <gerber_dir> <pads.csv>")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    csv_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('output/pads.csv')
    
    if not csv_path.exists():
        print(f"❌ CSV 文件不存在: {csv_path}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("孔位准确性验证工具")
    print("=" * 60)
    print(f"输入: {input_path}")
    print(f"CSV:  {csv_path}")
    
    # 执行验证
    if input_path.is_file():
        result = validate_single_file(input_path, csv_path)
    elif input_path.is_dir():
        result = validate_multi_layer(input_path, csv_path)
    else:
        print(f"❌ 无效路径: {input_path}")
        sys.exit(1)
    
    # 随机抽样
    visual_spot_check(csv_path, sample_size=10)
    
    # 总结
    if result:
        print("\n" + "=" * 60)
        print("验证总结")
        print("=" * 60)
        
        if result['accuracy'] >= 95:
            print("✅ 准确率优秀 (>= 95%)")
            print("   孔位提取非常准确，可以放心使用")
        elif result['accuracy'] >= 85:
            print("✓ 准确率良好 (85-95%)")
            print("   孔位提取基本准确，少量差异可能是:")
            print("   - 不同层的焊盘重叠")
            print("   - 容差范围内的微小偏移")
        elif result['accuracy'] >= 70:
            print("⚠️  准确率一般 (70-85%)")
            print("   建议检查:")
            print("   - Gerber 文件是否完整")
            print("   - 是否有特殊的 Aperture 类型")
            print("   - 提取逻辑是否需要调整")
        else:
            print("❌ 准确率较低 (< 70%)")
            print("   可能存在严重问题:")
            print("   - Gerber 文件格式不兼容")
            print("   - 提取逻辑有 bug")
            print("   - 坐标系转换错误")
        
        print(f"\n关键指标:")
        print(f"  准确率: {result['accuracy']:.1f}%")
        print(f"  匹配数: {result['matched']}/{result['total_ref']}")
        print(f"  遗漏数: {len(result['unmatched_ref'])}")
        print(f"  误提取: {len(result['unmatched_ext'])}")


if __name__ == '__main__':
    main()
