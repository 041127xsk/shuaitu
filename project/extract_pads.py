#!/usr/bin/env python3
"""
PCB Gerber 焊点提取工具 - 多层板版
从 Gerber 文件中提取所有焊接位置（SMT pads, Through-hole pads, Via）
"""

import os
import sys
import csv
import argparse
from pathlib import Path
from collections import defaultdict

import gerbonara
from gerbonara import GerberFile

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import PatchCollection
import numpy as np
from PIL import Image
import io


VIA_SIZE_THRESHOLD = 0.8
TH_HOLE_THRESHOLD = 1.0


def detect_pad_type(size, shape):
    """
    根据几何特征推断 pad 类型
    """
    if not size:
        return 'smt_pad'
    
    width = size[0]
    height = size[1] if len(size) > 1 else width
    
    if shape in ['R', 'rect', 'O', 'obround']:
        if width >= TH_HOLE_THRESHOLD:
            return 'through_hole'
        return 'smt_pad'
    elif shape == 'C':
        if width < VIA_SIZE_THRESHOLD:
            return 'via'
        elif width < TH_HOLE_THRESHOLD:
            return 'through_hole'
        else:
            return 'through_hole'
    
    return 'smt_pad'


def extract_pads_from_layer(gerber_path):
    """
    从单个 Gerber 文件中提取所有 Flash 对象（焊点）
    """
    print(f"正在解析: {gerber_path}")
    
    try:
        layer = GerberFile.open(gerber_path)
    except Exception as e:
        print(f"解析错误 {gerber_path}: {e}")
        return []
    
    pads = []
    
    for obj in layer.objects:
        if type(obj).__name__ == 'Flash':
            x = obj.x
            y = obj.y
            aperture = obj.aperture
            apt_type = type(aperture).__name__
            
            if apt_type == 'CircleAperture':
                shape = 'C'
                width = height = aperture.diameter
            elif apt_type == 'RectangleAperture':
                shape = 'R'
                width = aperture.w
                height = aperture.h
            elif apt_type == 'OvalAperture':
                shape = 'O'
                width = aperture.w
                height = aperture.h
            else:
                shape = 'unknown'
                diameter = getattr(aperture, 'diameter', None)
                if diameter:
                    width = height = diameter
                else:
                    size = getattr(aperture, 'size', None)
                    if size:
                        width = size[0]
                        height = size[1] if len(size) > 1 else width
                    else:
                        width = height = 0
            
            pad_type = detect_pad_type((width, height), shape)
            
            pads.append({
                'x': x,
                'y': y,
                'type': pad_type,
                'shape': shape,
                'width': width,
                'height': height,
                'source': Path(gerber_path).name
            })
    
    return pads


def extract_all_pads(gerber_dir):
    """
    从多层 Gerber 文件中提取焊点
    """
    all_pads = []
    
    priority_files = ['mask1.gbr', 'mask2.gbr', 'via_plugging.gbr', 'drilldrw.gbr', 'lay1.gbr', 'lay4.gbr']
    
    for fname in priority_files:
        fpath = Path(gerber_dir) / fname
        if fpath.exists():
            pads = extract_pads_from_layer(str(fpath))
            all_pads.extend(pads)
    
    for fpath in Path(gerber_dir).glob('*.gbr'):
        if fpath.name not in priority_files:
            pads = extract_pads_from_layer(str(fpath))
            all_pads.extend(pads)
    
    return all_pads


def merge_pads(pads, tolerance=0.05):
    """
    合并重复的焊点（基于位置）
    """
    merged = []
    seen = {}
    
    for pad in pads:
        key = (round(pad['x'] / tolerance), round(pad['y'] / tolerance))
        
        if key in seen:
            existing = seen[key]
            if pad['type'] == 'smt_pad' and existing['type'] != 'smt_pad':
                existing['type'] = 'smt_pad'
            existing['width'] = max(existing['width'], pad['width'])
            existing['height'] = max(existing['height'], pad['height'])
            existing['source'] += f",{pad['source']}"
        else:
            seen[key] = pad
            merged.append(pad)
    
    return merged


def save_to_csv(pads, output_path):
    """
    保存焊点到 CSV 文件
    """
    fieldnames = ['x', 'y', 'type', 'shape', 'width', 'height']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in pads:
            writer.writerow({k: p[k] for k in fieldnames})
    
    print(f"已保存到: {output_path}")


def render_gerber_with_overlay(gerber_dir, pads, output_path, base_layer='mask1.gbr'):
    """
    渲染 Gerber 图像并叠加焊点标记
    """
    gerber_path = Path(gerber_dir) / base_layer
    
    if not gerber_path.exists():
        print(f"找不到基础层: {gerber_path}")
        return False
    
    try:
        layer = GerberFile.open(str(gerber_path))
        
        bbox = layer.bounding_box()
        width_mm = bbox[1][0] - bbox[0][0]
        height_mm = bbox[1][1] - bbox[0][1]
        
        fig, ax = plt.subplots(figsize=(10, 10 * height_mm / width_mm), dpi=100)
        
        ax.set_xlim(bbox[0][0], bbox[1][0])
        ax.set_ylim(bbox[0][1], bbox[1][1])
        
        for obj in layer.objects:
            if type(obj).__name__ == 'Line':
                ax.plot([obj.p1[0], obj.p2[0]], [obj.p1[1], obj.p2[1]], 
                       'k-', linewidth=0.2)
            elif type(obj).__name__ == 'Flash':
                x, y = obj.x, obj.y
                apt = obj.aperture
                apt_type = type(apt).__name__
                
                if apt_type == 'CircleAperture':
                    r = apt.diameter / 2
                    circle = plt.Circle((x, y), r, color='#444444', alpha=0.6, fill=True)
                    ax.add_patch(circle)
                elif apt_type == 'RectangleAperture':
                    w, h = apt.w, apt.h
                    rect = patches.Rectangle((x-w/2, y-h/2), w, h, 
                                            color='#444444', alpha=0.6, fill=True)
                    ax.add_patch(rect)
        
        for pad in pads:
            ax.plot(pad['x'], pad['y'], 'o', color='red', markersize=3, 
                   markeredgecolor='darkred', markeredgewidth=0.5, alpha=0.9)
        
        ax.set_aspect('equal')
        ax.axis('off')
        ax.invert_yaxis()
        
        plt.tight_layout(pad=0)
        plt.savefig(output_path, dpi=100, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"叠加图已保存到: {output_path}")
        return True
        
    except Exception as e:
        import traceback
        print(f"渲染错误: {e}")
        traceback.print_exc()
        return False


def visualize_pads(pads, output_path, title="PCB Solder Points"):
    """
    使用 matplotlib 可视化焊点
    """
    if not pads:
        print("没有焊点可可视化")
        return
    
    fig, ax = plt.subplots(figsize=(14, 12))
    
    smt_pads = [p for p in pads if p['type'] == 'smt_pad']
    th_pads = [p for p in pads if p['type'] == 'through_hole']
    vias = [p for p in pads if p['type'] == 'via']
    
    colors = {
        'smt_pad': '#2ecc71',
        'through_hole': '#e74c3c', 
        'via': '#3498db'
    }
    labels = {
        'smt_pad': f'SMT Pad ({len(smt_pads)})',
        'through_hole': f'Through-hole ({len(th_pads)})', 
        'via': f'Via ({len(vias)})'
    }
    
    for pad in pads:
        pt = pad['type']
        color = colors[pt]
        
        if pad['shape'] in ['R', 'rect']:
            w, h = pad['width'], pad['height']
            rect = patches.Rectangle(
                (pad['x'] - w/2, pad['y'] - h/2), w, h,
                linewidth=0.5, edgecolor='black', 
                facecolor=color, alpha=0.7
            )
            ax.add_patch(rect)
        else:
            r = pad['width'] / 2
            circle = patches.Circle(
                (pad['x'], pad['y']), r,
                linewidth=0.5, edgecolor='black',
                facecolor=color, alpha=0.7
            )
            ax.add_patch(circle)
    
    xs = [p['x'] for p in pads]
    ys = [p['y'] for p in pads]
    
    if xs and ys:
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        x_margin = x_range * 0.1 if x_range > 0 else 10
        y_margin = y_range * 0.1 if y_range > 0 else 10
        
        ax.set_xlim(min(xs) - x_margin, max(xs) + x_margin)
        ax.set_ylim(min(ys) - y_margin, max(ys) + y_margin)
    
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_title(title, fontsize=14)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3, linestyle='--')
    
    legend_patches = [
        patches.Patch(color=colors[t], label=labels[t]) 
        for t in colors.keys() 
        if any(p['type'] == t for p in pads)
    ]
    ax.legend(handles=legend_patches, loc='upper right', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"可视化已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='从 Gerber 文件提取焊点')
    parser.add_argument('--dir', '-d', default='gerber', 
                        help='Gerber 文件目录')
    parser.add_argument('--output', '-o', default='output/solder_points.csv',
                        help='输出 CSV 路径')
    parser.add_argument('--visual', '-v', default='output/solder_points.png',
                        help='可视化输出路径')
    parser.add_argument('--overlay', default='output/overlay.png',
                        help='Gerber+焊点叠加图输出路径')
    parser.add_argument('--layer', default='mask1.gbr',
                        help='用于渲染的基础 Gerber 层')
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    gerber_dir = script_dir / args.dir
    output_csv = script_dir / args.output
    output_png = script_dir / args.visual
    output_overlay = script_dir / args.overlay
    
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_overlay.parent.mkdir(parents=True, exist_ok=True)
    
    if not gerber_dir.exists():
        print(f"错误: 目录不存在: {gerber_dir}")
        sys.exit(1)
    
    print("=" * 50)
    print("PCB 焊点提取工具 - 多层板版")
    print("=" * 50)
    
    all_pads = extract_all_pads(str(gerber_dir))
    print(f"\n原始提取: {len(all_pads)} 个焊点")
    
    merged_pads = merge_pads(all_pads)
    print(f"合并后: {len(merged_pads)} 个焊点")
    
    if not merged_pads:
        print("未找到任何焊点")
        sys.exit(1)
    
    smt_count = sum(1 for p in merged_pads if p['type'] == 'smt_pad')
    th_count = sum(1 for p in merged_pads if p['type'] == 'through_hole')
    via_count = sum(1 for p in merged_pads if p['type'] == 'via')
    
    print(f"\n焊点统计:")
    print(f"  ├── SMT Pads: {smt_count}")
    print(f"  ├── Through-hole: {th_count}")
    print(f"  └── Via: {via_count}")
    print(f"  └── 总计: {len(merged_pads)}")
    
    save_to_csv(merged_pads, output_csv)
    visualize_pads(merged_pads, output_png, title="8029 PCB Solder Points")
    
    print("\n正在渲染 Gerber 图像...")
    render_gerber_with_overlay(str(gerber_dir), merged_pads, str(output_overlay), args.layer)
    
    print("\n完成!")


if __name__ == '__main__':
    main()