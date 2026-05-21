#!/usr/bin/env python3
"""
PCB Gerber 焊盘提取工具
从 Gerber 文件中提取所有焊盘（Flash 对象）
"""

import os
import sys
import csv
import warnings
from pathlib import Path

import gerbonara
from gerbonara import GerberFile
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np


def extract_pads(gerber_path):
    """
    从 Gerber 文件中提取所有 Flash 对象（焊盘）
    """
    try:
        layer = GerberFile.open(gerber_path)
    except Exception as e:
        print(f"解析错误: {gerber_path} - {e}")
        return []
    
    pads = []
    for obj in layer.objects:
        if type(obj).__name__ != 'Flash':
            continue
            
        x, y = obj.x, obj.y
        apt = obj.aperture
        apt_type = type(apt).__name__
        
        if apt_type == 'CircleAperture':
            shape = 'circle'
            width = height = apt.diameter
        elif apt_type == 'RectangleAperture':
            shape = 'rect'
            width = apt.w
            height = apt.h
        elif apt_type == 'OvalAperture':
            shape = 'oval'
            width = apt.w
            height = apt.h
        else:
            shape = 'unknown'
            diameter = getattr(apt, 'diameter', None)
            if diameter:
                width = height = diameter
            else:
                size = getattr(apt, 'size', None)
                if size:
                    width = size[0]
                    height = size[1] if len(size) > 1 else width
                else:
                    width = height = 0
        
        pads.append({
            'x': x,
            'y': y,
            'shape': shape,
            'width': width,
            'height': height
        })
    
    return pads


def cluster_pads(pads, threshold=3.0):
    """
    基于距离阈值对焊盘进行聚类
    """
    if not pads:
        return []
    
    coords = np.array([[p['x'], p['y']] for p in pads])
    n = len(coords)
    visited = [False] * n
    clusters = []
    
    for i in range(n):
        if visited[i]:
            continue
        
        cluster = [i]
        queue = [i]
        visited[i] = True
        
        while queue:
            j = queue.pop(0)
            for k in range(n):
                if not visited[k]:
                    dist = np.linalg.norm(coords[j] - coords[k])
                    if dist < threshold:
                        visited[k] = True
                        cluster.append(k)
                        queue.append(k)
        
        clusters.append({
            'indices': cluster,
            'x_min': coords[cluster, 0].min(),
            'x_max': coords[cluster, 0].max(),
            'y_min': coords[cluster, 1].min(),
            'y_max': coords[cluster, 1].max(),
            'count': len(cluster),
            'center_x': coords[cluster, 0].mean(),
            'center_y': coords[cluster, 1].mean()
        })
    
    return clusters


def guess_component_type(cluster, pads):
    """
    根据焊盘数量和分布推测元件封装类型
    """
    count = cluster['count']
    width = cluster['x_max'] - cluster['x_min']
    height = cluster['y_max'] - cluster['y_min']
    aspect = max(width, height) / min(width, height) if min(width, height) > 0 else 1
    
    if count == 2:
        if aspect > 3:
            return 'Resistor/Capacitor 0402'
        elif aspect > 1.5:
            return 'Resistor/Capacitor 0603'
        else:
            return 'Resistor/Capacitor'
    elif 4 <= count <= 8:
        return 'SOP/TSOP'
    elif count == 16:
        return 'QFP-16'
    elif count == 24:
        return 'QFP-24'
    elif count == 32:
        return 'QFP-32'
    elif count == 44:
        return 'QFP-44'
    elif count == 48:
        return 'QFP-48'
    elif count == 64:
        return 'QFP-64'
    elif 8 < count < 20:
        return 'QFN'
    elif count >= 20 and aspect > 2:
        return 'BGA/QFN'
    else:
        return 'Unknown'


def save_pads_csv(pads, output_path):
    """保存焊盘到 CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['x', 'y', 'shape', 'width', 'height'])
        writer.writeheader()
        writer.writerows(pads)
    print(f"已保存: {output_path}")


def save_components_csv(clusters, pads, output_path):
    """保存元件到 CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['component_type', 'pad_count', 'center_x', 'center_y', 'x_min', 'x_max', 'y_min', 'y_max'])
        writer.writeheader()
        for c in clusters:
            comp_type = guess_component_type(c, pads)
            writer.writerow({
                'component_type': comp_type,
                'pad_count': c['count'],
                'center_x': round(c['center_x'], 2),
                'center_y': round(c['center_y'], 2),
                'x_min': round(c['x_min'], 2),
                'x_max': round(c['x_max'], 2),
                'y_min': round(c['y_min'], 2),
                'y_max': round(c['y_max'], 2)
            })
    print(f"已保存: {output_path}")


def visualize_pads(pads, output_path, title="PCB Pads"):
    """绘制焊盘可视化图"""
    if not pads:
        print("没有焊盘可绘制")
        return
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    for p in pads:
        if p['shape'] == 'rect':
            rect = patches.Rectangle(
                (p['x'] - p['width']/2, p['y'] - p['height']/2),
                p['width'], p['height'],
                linewidth=0.5, edgecolor='black',
                facecolor='#3498db', alpha=0.7
            )
            ax.add_patch(rect)
        else:
            circle = patches.Circle(
                (p['x'], p['y']), p['width']/2,
                linewidth=0.5, edgecolor='black',
                facecolor='#3498db', alpha=0.7
            )
            ax.add_patch(circle)
    
    xs = [p['x'] for p in pads]
    ys = [p['y'] for p in pads]
    
    if xs and ys:
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        margin = max(x_range, y_range) * 0.1
        ax.set_xlim(min(xs) - margin, max(xs) + margin)
        ax.set_ylim(min(ys) - margin, max(ys) + margin)
    
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_title(f"{title} - {len(pads)} pads")
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"已保存: {output_path}")


def main():
    script_dir = Path(__file__).parent
    gerber_dir = script_dir / 'gerber'
    output_dir = script_dir / 'output'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not gerber_dir.exists():
        print(f"错误: 目录不存在: {gerber_dir}")
        print("请将 Gerber 文件放入 gerber/ 文件夹")
        sys.exit(1)
    
    gerber_files = list(gerber_dir.glob('*.gbr')) + list(gerber_dir.glob('*.gtl')) + \
                   list(gerber_dir.glob('*.gbl')) + list(gerber_dir.glob('*.gbs')) + \
                   list(gerber_dir.glob('*.gbo')) + list(gerber_dir.glob('*.gml'))
    
    if not gerber_files:
        print(f"错误: 目录 {gerber_dir} 中没有 Gerber 文件")
        sys.exit(1)
    
    print("=" * 50)
    print("PCB 焊盘提取工具")
    print("=" * 50)
    
    all_pads = []
    for gf in gerber_files:
        pads = extract_pads(str(gf))
        print(f"从 {gf.name} 提取: {len(pads)} 个焊盘")
        all_pads.extend(pads)
    
    print(f"\n总计提取: {len(all_pads)} 个焊盘")
    
    shapes = {}
    for p in all_pads:
        shapes[p['shape']] = shapes.get(p['shape'], 0) + 1
    print(f"形状分布: {shapes}")
    
    save_pads_csv(all_pads, output_dir / 'pads.csv')
    
    print("\n正在进行聚类分析...")
    clusters = cluster_pads(all_pads, threshold=2.0)
    print(f"识别出 {len(clusters)} 个元件/区域")
    
    save_components_csv(clusters, all_pads, output_dir / 'components.csv')
    
    visualize_pads(all_pads, output_dir / 'pads.png', title="All Pads")
    
    print("\n完成!")
    print(f"\n输出文件:")
    print(f"  - {output_dir / 'pads.csv'}")
    print(f"  - {output_dir / 'pads.png'}")
    print(f"  - {output_dir / 'components.csv'}")


if __name__ == '__main__':
    main()