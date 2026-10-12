# -*- coding: utf-8 -*-
"""离线纯函数单测（仅标准库，不联网、不读密钥）。

覆盖各工具脚本中可独立验证的纯函数：
- providers/modelscope/工具集/fetch_data.py        safe_filename / detect_stability / is_base_model / parse_fee
- providers/modelscope/工具集/probe_supplement.py  gen_candidates + 探测留痕读写
- providers/openrouter/工具集/build_report.py      ctx_h / _key_tail（无密钥时）
- providers/openrouter/工具集/openrouter_connectivity_test.py  arg_value

运行：python -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def _load(mod_name, rel_parts):
    """按文件路径加载被测模块（目录名含中文，不能用包导入）。"""
    path = os.path.join(ROOT, *rel_parts)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(path))  # probe_supplement 需同目录 import fetch_data
    spec.loader.exec_module(mod)
    return mod

_FD = _load("fd_ut", ("providers", "modelscope", "工具集", "fetch_data.py"))
_PS = _load("ps_ut", ("providers", "modelscope", "工具集", "probe_supplement.py"))
_BR = _load("br_ut", ("providers", "openrouter", "工具集", "build_report.py"))
_OCT = _load("oct_ut", ("providers", "openrouter", "工具集", "openrouter_connectivity_test.py"))

class TestFetchDataPure(unittest.TestCase):
    def test_safe_filename(self):
        self.assertEqual(_FD.safe_filename("deepseek-ai/DeepSeek-V3.2"),
                         "deepseek-ai_DeepSeek-V3.2")

    def test_detect_stability(self):
        self.assertEqual(_FD.detect_stability("ZhipuAI/GLM-5.3-Flash"), "稳定")
        self.assertEqual(_FD.detect_stability("deepseek-ai/DeepSeek-V4-Flash-Vision-Exp"),
                         "实验/预览")

    def test_is_base_model(self):
        self.assertTrue(_FD.is_base_model("PaddlePaddle/ERNIE-4.5-0.3B-PT"))
        self.assertFalse(_FD.is_base_model("deepseek-ai/DeepSeek-V3.2"))

    def test_parse_fee_moshi(self):
        body = json.dumps({"Data": {"Providers": [
            {"ChineseName": "魔搭社区", "EstimatedMagicGrainCost": 2, "CostTier": "ultra"},
            {"Name": "ThirdParty", "EstimatedMagicGrainCost": None, "CostTier": ""},
        ]}}, ensure_ascii=False)
        fee = _FD.parse_fee(body)
        self.assertEqual(fee["magic_cost"], 2)
        self.assertEqual(fee["cost_tier"], "ultra")
        self.assertIn("魔搭社区:2魔粒/ultra", fee["providers"])

class TestProbeSupplement(unittest.TestCase):
    def test_gen_candidates_variants(self):
        self.assertIn("deepseek-ai/DeepSeek-V4-Flash",
                      _PS.gen_candidates("deepseek-ai/DeepSeek-V4"))

    def test_gen_candidates_no_self(self):
        cands = _PS.gen_candidates("deepseek-ai/DeepSeek-V4")
        self.assertNotIn("deepseek-ai/DeepSeek-V4", cands)

    def test_gen_candidates_invalid_seed(self):
        self.assertEqual(_PS.gen_candidates("no-slash-id"), [])

    def test_probe_history_roundtrip(self):
        old = _PS.PROBE_HISTORY
        try:
            with tempfile.TemporaryDirectory() as td:
                _PS.PROBE_HISTORY = os.path.join(td, "h.jsonl")
                _PS.append_probe_history("a/b", "dead")
                _PS.append_probe_history("c/d", "free")
                self.assertEqual(_PS.load_probe_history(), {"a/b"})
        finally:
            _PS.PROBE_HISTORY = old

class TestBuildReport(unittest.TestCase):
    def test_ctx_h(self):
        self.assertEqual(_BR.ctx_h(None), "-")
        self.assertEqual(_BR.ctx_h(4096), "4K")
        self.assertEqual(_BR.ctx_h(2_000_000), "2M")

    def test_key_tail_without_secret(self):
        # 无环境变量、无 local_secret.py 时应返回空串（源码正则兜底已删除，
        # 不再把源码 docstring 里的 "sk-or-v1-..." 占位符当成密钥尾巴）。
        self.assertEqual(_BR._key_tail(), "")

class TestOpenrouterArgValue(unittest.TestCase):
    def test_arg_value(self):
        old = sys.argv
        try:
            sys.argv = ["prog", "--only=a,b"]
            self.assertEqual(_OCT.arg_value("only"), "a,b")
            sys.argv = ["prog"]
            self.assertIsNone(_OCT.arg_value("only"))
        finally:
            sys.argv = old

if __name__ == "__main__":
    unittest.main()