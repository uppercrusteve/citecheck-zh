# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.1.0] - 2026-11-17

### Added

- 顺序编码与著者-年份引用解析，支持半角/全角括号、逗号/顿号分隔与编号范围展开。
- 10 条结构检查规则 C01–C10：悬空引用、未被引用条目、重复条目、越界/断档/首现顺序、缺年份条目、混用引用制、坏 DOI、缺文献区、超长引用组、缺年份引用。
- Rich 终端表格与 JSON 报告；`--min-level`、`--color`、`-o/--output`、`--force`。
- `renumber` 子命令：按首次出现重排顺序编码并重建文献表，压缩连续编号。
- `init` 子命令：生成覆盖全部 10 条规则的合成演示稿。
- 退出码约定：0 无错误、1 有 error、2 输入/输出错误。
- 合成示例 `examples/clean.md`（零发现）与 `examples/seed_errors.md`（命中 C01–C10）。
- 63 个 pytest 测试，覆盖规则正反例、解析边界、重排与 CLI。
- Ubuntu/Windows、Python 3.11/3.12 的 GitHub Actions CI。
- 方法、判据、误报边界与局限文档 `docs/methods.md`。

[Unreleased]: https://github.com/uppercrusteve/citecheck-zh/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/uppercrusteve/citecheck-zh/releases/tag/v0.1.0
