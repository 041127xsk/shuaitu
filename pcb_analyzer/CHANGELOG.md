# 更新日志 (CHANGELOG)

## v1.1 (当前版本)

### 新增功能

#### Excellon 钻孔文件支持 (drill_extractor.py)
- 实现 `DrillExtractor` 类，使用 gerbonara 解析 Excellon 文件
- 支持圆形钻孔和槽孔提取
- 自动推断镀层状态 (PTH/NPTH)
- 支持扩展名: .drl, .ncd, .xln, .txt, .drd, .dri, .nc
- 钻孔数据与焊盘匹配，识别通孔元件

#### 通孔/贴片元件识别
- clustering.py 新增 `drills` 参数，集成钻孔数据
- 聚类结果新增 `mount_type`, `has_drill`, `drill_count`, `plated_drill_count` 字段
- 自动区分通孔 (through-hole) 和贴片 (smd) 元件

#### 测试
- 新增 `tests/test_drill_extractor.py` (10 个测试用例)
- 共 39 个单元测试，全部通过

### 改进

- main.py 新增 `--no-drills` 参数跳过钻孔提取
- components.csv 输出包含安装类型信息
- 镀层状态推断优先检查非镀通孔关键词 (NPTH > PTH)

## v1.0

### 新增功能

#### 封装库系统 (package_library.py)
- 实现 `PackageDefinition` / `ClusterFeatures` / `RecognitionResult` 数据模型
- 实现 `ConfigLoader` — 支持 JSON 和 YAML 配置加载
- 实现 `ComponentLibrarySystem` — 默认库 56 个封装定义，支持自定义库覆盖
- 实现 `RecognitionEngine` — 基于特征的封装匹配引擎，6 维度加权置信度评分
- 默认库外挂为 `config/packages/default_library.json`，用户可直接编辑

#### 元件识别提升
- 新增识别类型：SOD/SOT/DPAK 等分立器件、排针连接器、USB/HDMI/RJ45
- 支持布局模式检测（single/dual/quad/grid）
- 支持引脚间距计算和匹配
- 分类输出：`confidence`, `category`, `package_id` 字段

#### Pick & Place 生成 (pnp.py)
- IPC-9751 标准格式输出
- 自动位号分配（R=电阻, U=IC, X=连接器）
- 基于包围盒的旋转角度推断
- PNP 文件准确性验证 (validate_pnp.py)

#### 可视化增强
- 置信度着色图 `confidence.png`（绿=高, 黄=中, 红=低）
- PNP 位号标注验证图

#### 配置文件示例
- `config/packages/example.json` — JSON 格式示例
- `config/packages/example.yaml` — YAML 格式示例
- `config/packages/template.json` — 空白模板

#### 测试与验证
- 新增 `tests/test_config_loader.py` (9 个测试用例)
- 新增 `tests/test_recognition_engine.py` (8 个测试用例)
- 新增 `tests/test_library_system.py` (12 个测试用例)
- 新增 `tools/validate_accuracy.py` — 对比 ground truth 验证准确率
- 共 29 个单元测试，全部通过

### 改进

- main.py 新增 `--package-lib`, `--list-packages`, `--validate-config` 参数
- clustering.py 保持向后兼容，library_system=None 时使用旧逻辑
- requirements.txt 新增 pyyaml, pytest

### 修复

- 修复 Windows GBK 编码下 Unicode 字符输出问题
- 修复多个丝印文件无 Flash 时的空数据处理

## v0.x (初始版本)

- 基础 Gerber 解析和焊盘提取
- BFS 空间聚类
- 硬编码元件识别规则
- 基本可视化输出
