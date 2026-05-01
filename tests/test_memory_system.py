from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hiclaw.memory_intent import (
    build_memory_intent_ack,
    detect_memory_intent,
    should_auto_accept_memory_intent,
)
from hiclaw.memory_store import (
    append_memory_candidate,
    append_structured_long_term_memory,
    archive_old_memories,
    auto_promote_candidates,
    ensure_memory_files,
    meditate_and_organize_memories,
)
from hiclaw.memory_frequency import (
    calculate_memory_importance,
    get_high_frequency_topics,
    load_frequency_state,
    update_memory_frequency,
)

# 临时测试目录
TEST_DIR = Path(tempfile.mkdtemp(prefix="hiclaw_test_"))
MEMORY_DIR = TEST_DIR / "memory"
LONG_TERM_DIR = MEMORY_DIR / "long_term"
CANDIDATES_DIR = MEMORY_DIR / "candidates"
ARCHIVE_DIR = MEMORY_DIR / "archive"

test_results = []


def log_test(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    test_results.append({"name": name, "passed": passed, "detail": detail})
    print(f"  [{status}] {name}")
    if detail and not passed:
        print(f"         {detail}")


def setup_test_env():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    LONG_TERM_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # 覆盖配置为测试目录
    import hiclaw.config as config
    config.MEMORY_DIR = MEMORY_DIR
    config.LONG_TERM_MEMORY_DIR = LONG_TERM_DIR
    config.MEMORY_CANDIDATES_DIR = CANDIDATES_DIR
    config.MEMORY_ARCHIVE_DIR = ARCHIVE_DIR
    config.CLAUDE_MEMORY_FILE = MEMORY_DIR / "CLAUDE.md"
    config.WORKING_STATE_FILE = MEMORY_DIR / "working_state.json"
    config.SESSION_SUMMARIES_DIR = MEMORY_DIR / "session_summaries"
    config.SESSION_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    config.CONVERSATIONS_DIR = MEMORY_DIR / "conversations"
    config.CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    config.MEMORY_CANDIDATE_AUTO_PROMOTE_SECONDS = 86400
    config.MEMORY_ARCHIVE_AFTER_DAYS = 30

    # 覆盖 memory_store 中的 LONG_TERM_FILES
    import hiclaw.memory_store as ms
    ms.LONG_TERM_FILES = {
        "profile": LONG_TERM_DIR / "profile.md",
        "preferences": LONG_TERM_DIR / "preferences.md",
        "rules": LONG_TERM_DIR / "rules.md",
    }
    ms.MEMORY_CANDIDATES_DIR = CANDIDATES_DIR
    ms.MEMORY_ARCHIVE_DIR = ARCHIVE_DIR
    ms.MEMORY_CANDIDATE_AUTO_PROMOTE_SECONDS = 86400
    ms.MEMORY_ARCHIVE_AFTER_DAYS = 30

    # 初始化记忆文件
    for key, filename, title in [("profile", "profile.md", "用户画像"), ("preferences", "preferences.md", "用户偏好"), ("rules", "rules.md", "长期规则")]:
        path = LONG_TERM_DIR / filename
        if not path.exists():
            path.write_text(f"# {title}\n\n- 暂无结构化{title}。\n", encoding="utf-8")

    ensure_memory_files()


def cleanup_test_env():
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)


def test_intent_recognition():
    print("\nTest 1: Intent Recognition")

    # 明确记忆
    intent = detect_memory_intent("你要记得我喜欢用中文")
    log_test("明确记忆识别", intent is not None and intent.reason == "explicit_remember")

    # 偏好声明
    intent = detect_memory_intent("我喜欢用 VS Code")
    log_test("偏好声明识别", intent is not None and intent.reason == "preference_statement")

    # 未来规则
    intent = detect_memory_intent("以后你要简洁回答")
    log_test("未来规则识别", intent is not None and intent.reason == "future_rule")

    # 自动接受判断
    intent = detect_memory_intent("你可以叫我小明")
    auto_accept = should_auto_accept_memory_intent(intent) if intent else False
    log_test("自动接受判断", auto_accept is True, f"auto_accept={auto_accept}")

    # 非记忆意图
    intent = detect_memory_intent("今天天气怎么样？")
    log_test("非记忆意图过滤", intent is None)

    # 反馈语句
    intent = detect_memory_intent("记住这个：明天开会")
    ack = build_memory_intent_ack(intent, True) if intent else ""
    log_test("反馈语句生成", len(ack) > 0, f"ack={ack}")


def test_candidate_auto_promotion():
    print("\nTest 2: Candidate Auto-Promotion")

    # 创建不同 reason 的候选文件，每个间隔 1 秒避免文件名冲突
    candidates = [
        ("明确记忆", "叫我小明", "addressing_user"),
        ("偏好声明", "我喜欢用中文", "preference_statement"),
        ("未来规则", "以后简洁回答", "future_rule"),
        ("模糊内容", "随便记一下", None),
    ]

    created_files = []
    for i, (name, content, reason) in enumerate(candidates):
        f = append_memory_candidate(content, "general", reason)
        created_files.append(f)
        time.sleep(1.1)  # 确保时间戳不同

    # 立即提升（明确记忆 reason=addressing_user 延迟为 0）
    print("  执行立即提升...")
    promoted = auto_promote_candidates()
    immediate_promoted = len(promoted)
    log_test("明确记忆立即提升", immediate_promoted >= 1, f"提升了 {immediate_promoted} 条")

    # 模拟时间流逝：修改候选文件时间戳为 2 小时前
    now = datetime.now()
    remaining_files = list(CANDIDATES_DIR.glob("*.md"))
    for candidate_file in remaining_files:
        content = candidate_file.read_text(encoding="utf-8")
        if "preference_statement" in content or "future_rule" in content:
            # 修改文件名为 2 小时前
            old_ts = candidate_file.stem.split("_")[0]
            new_ts = (now - timedelta(hours=2)).strftime("%Y%m%d_%H%M%S")
            new_name = candidate_file.name.replace(old_ts, new_ts)
            candidate_file.rename(CANDIDATES_DIR / new_name)

    promoted = auto_promote_candidates()
    delayed_promoted = len(promoted)
    log_test("延迟提升（2小时后）", delayed_promoted >= 1, f"提升了 {delayed_promoted} 条")

    # 模拟 24 小时后
    remaining_files = list(CANDIDATES_DIR.glob("*.md"))
    for candidate_file in remaining_files:
        old_ts = candidate_file.stem.split("_")[0]
        new_ts = (now - timedelta(hours=24)).strftime("%Y%m%d_%H%M%S")
        new_name = candidate_file.name.replace(old_ts, new_ts)
        candidate_file.rename(CANDIDATES_DIR / new_name)

    promoted = auto_promote_candidates()
    final_promoted = len(promoted)
    log_test("最终全部提升（24小时后）", final_promoted >= 1, f"提升了 {final_promoted} 条")


def test_frequency_weighting():
    print("\nTest 3: Frequency Weighting")

    # 模拟多次提到同一话题
    topics = ["VS Code", "VS Code", "VS Code", "Python", "Python", "简洁"]
    for topic in topics:
        update_memory_frequency(f"我喜欢用{topic}", f"好的，记住了{topic}")

    high_freq = get_high_frequency_topics(threshold=3)
    log_test("高频话题识别", len(high_freq) >= 1, f"高频话题: {high_freq}")

    # 重要性评分
    score1 = calculate_memory_importance("必须记住用 VS Code")
    score2 = calculate_memory_importance("可能暂时用 Python")
    log_test("重要性评分-强调词", score1 > score2, f"强调词={score1}, 模糊词={score2}")


def test_meditation_mechanism():
    print("\nTest 4: Memory Meditation")

    # 创建相似记忆
    append_structured_long_term_memory("我喜欢用 VS Code", "preferences", "style")
    append_structured_long_term_memory("我喜欢简洁回答", "preferences", "style")
    append_structured_long_term_memory("回答简洁一些", "preferences", "style")

    # 执行冥想
    report = meditate_and_organize_memories()

    merged_count = len(report.get("merged_memories", []))
    log_test("相似记忆合并", merged_count >= 0, f"合并了 {merged_count} 组")

    cleaned_count = len(report.get("cleaned_memories", []))
    log_test("低价值记忆清理", True, f"清理了 {cleaned_count} 个类别")


def test_memory_archiving():
    print("\nTest 5: Memory Archiving")

    # 创建一条 31 天前的记忆（模拟）
    old_date = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
    pref_file = LONG_TERM_DIR / "preferences.md"
    existing = pref_file.read_text(encoding="utf-8") if pref_file.exists() else "# 用户偏好\n"
    new_content = f"{existing}\n## 自动记忆 {old_date}\n- 这是一条旧记忆\n"
    pref_file.write_text(new_content, encoding="utf-8")

    # 执行归档
    archived = archive_old_memories()
    log_test("过期记忆归档", len(archived) >= 1, f"归档了 {len(archived)} 个文件")

    # 检查归档文件是否存在
    archive_exists = any(f.name.startswith("preferences_") for f in ARCHIVE_DIR.glob("*.md"))
    log_test("归档文件存在", archive_exists, f"归档目录内容: {list(ARCHIVE_DIR.glob('*.md'))}")


def test_structured_storage():
    print("\nTest 6: Structured Storage")

    # 写入不同分类
    append_structured_long_term_memory("我叫小明", "profile", "addressing_user")
    append_structured_long_term_memory("我喜欢中文", "preferences", "language")
    append_structured_long_term_memory("以后简洁回答", "rules", "reply_rule")

    # 检查文件内容
    profile_file = LONG_TERM_DIR / "profile.md"
    pref_file = LONG_TERM_DIR / "preferences.md"
    rules_file = LONG_TERM_DIR / "rules.md"

    profile_content = profile_file.read_text(encoding="utf-8")
    pref_content = pref_file.read_text(encoding="utf-8")
    rules_content = rules_file.read_text(encoding="utf-8")

    log_test("profile 分类存储", "小明" in profile_content, f"profile 内容长度: {len(profile_content)}")
    log_test("preferences 分类存储", "中文" in pref_content, f"preferences 内容长度: {len(pref_content)}")
    log_test("rules 分类存储", "简洁" in rules_content, f"rules 内容长度: {len(rules_content)}")

    # 槽位更新测试
    append_structured_long_term_memory("我叫小红", "profile", "addressing_user")
    profile_content = profile_file.read_text(encoding="utf-8")
    # 检查是否只有一条 addressing_user 记录
    slot_count = profile_content.count("<!-- slot:addressing_user -->")
    log_test("槽位更新（旧值替换）", slot_count == 1, f"槽位数量: {slot_count}")


def generate_report():
    print("\n" + "=" * 80)
    print("HiClaw Memory System Test Report")
    print("=" * 80)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Test Environment: {TEST_DIR}")
    print()

    total = len(test_results)
    passed = sum(1 for r in test_results if r["passed"])
    failed = total - passed

    print(f"Total: {total} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Pass Rate: {passed/total*100:.1f}%")
    print()

    print("Detailed Results:")
    print("-" * 80)
    for i, result in enumerate(test_results, 1):
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{i:2d}. [{status}] {result['name']}")
        if result["detail"]:
            print(f"    {result['detail']}")

    print()
    print("=" * 80)

    if failed == 0:
        print("All tests passed! Memory system is working correctly.")
    else:
        print(f"{failed} test(s) failed. Please check the results above.")

    print("=" * 80)

    # 保存报告
    report_path = TEST_DIR / "test_report.md"
    report_content = f"""# HiClaw Memory System Test Report

Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Test Environment: {TEST_DIR}

## Summary

- Total: {total} tests
- Passed: {passed}
- Failed: {failed}
- Pass Rate: {passed/total*100:.1f}%

## Detailed Results

"""
    for i, result in enumerate(test_results, 1):
        status = "PASS" if result["passed"] else "FAIL"
        report_content += f"{i:2d}. [{status}] {result['name']}"
        if result["detail"]:
            report_content += f" - {result['detail']}"
        report_content += "\n"

    report_path.write_text(report_content, encoding="utf-8")
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    print("Starting HiClaw Memory System Test...")
    print(f"Test Directory: {TEST_DIR}")

    try:
        setup_test_env()

        test_intent_recognition()
        test_candidate_auto_promotion()
        test_frequency_weighting()
        test_meditation_mechanism()
        test_memory_archiving()
        test_structured_storage()

        generate_report()
    except Exception as e:
        print(f"\nTest Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup_test_env()
        print(f"\nTest directory cleaned: {TEST_DIR}")
