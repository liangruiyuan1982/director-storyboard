import argparse
from pathlib import Path


def build_parser(step_defs):
    parser = argparse.ArgumentParser(description="Director Storyboard Pipeline")
    parser.add_argument("phase", nargs="?", choices=["0", "1", "2", "3", "4", "5", "full", "lookdev", "patch"], help="Phase")
    parser.add_argument("--project", required=True)
    parser.add_argument("--story", help="Path to story.txt (phase 0)")
    parser.add_argument("--model", choices=["glm51", "kimi25", "gemma4", "minimax"], help="必须显式指定模型")
    parser.add_argument("--confirm", action="store_true", help="Bypass gate waiting, assume confirmed")
    parser.add_argument("--patch", help="Partial modification instruction (e.g. 'B05+B06 merged')")
    parser.add_argument("--resume", action="store_true", help="Resume from completed checkpoints")
    parser.add_argument("--restart-from", choices=[step["key"] for step in step_defs], help="Force restart from a specific step")
    return parser


def resolve_project_dir(project, projects_dir):
    if "/" in project:
        return Path(project)
    return projects_dir / project


def run_full(args, project_dir, should_skip_step, run_step, process_gate, phase0_intent_capture, phase1_story_dna, phase2_beats, phase3_characters, phase4_cinematography, phase5_output, load_run_state, save_run_state, print_run_state_summary):
    print(f"🚀 全流程启动: {project_dir.name}{'（resume）' if args.resume else ''}")

    if args.story and not should_skip_step(project_dir, "phase0_input", args.resume, verbose=True):
        s = run_step("phase0_input", phase0_intent_capture, project_dir, args.story)
        if s == "waiting_intent":
            print("⏸ Phase 0: 请先完成意图问卷 → 写入 director_intent.json")
            return

    if not should_skip_step(project_dir, "phase1_story_dna", args.resume, verbose=True):
        run_step("phase1_story_dna", phase1_story_dna, project_dir, model=args.model)
    else:
        print("⏭ 跳过 Phase 1 Story DNA")

    if not should_skip_step(project_dir, "phase2_beats", args.resume, verbose=True):
        status = run_step("phase2_beats", phase2_beats, project_dir, model=args.model)
        if status == "waiting_gate":
            resolved = process_gate(project_dir, "Gate 0", "beats-viewer.html", confirm=args.confirm)
            if resolved == "await_detail":
                print("⏸ 请输入具体修改指令（如 --patch 'B05+B06 merged'）")
                return
    else:
        print("⏭ 跳过 Phase 2 Beats（已完成且已审核）")

    if not should_skip_step(project_dir, "phase3_characters", args.resume, verbose=True):
        status = run_step("phase3_characters", phase3_characters, project_dir, model=args.model)
        if status == "waiting_gate":
            resolved = process_gate(project_dir, "Gate 1", "character-viewer.html", confirm=args.confirm)
            if resolved == "await_detail":
                print("⏸ 等待角色修改指令")
                return
    else:
        print("⏭ 跳过 Phase 3 Characters（已完成且已审核）")

    need_phase4 = any(not should_skip_step(project_dir, step, args.resume, verbose=True) for step in [
        "phase4a_lookdev", "phase4b_color_script", "phase4c_photography", "phase4d_acting", "phase4e_panels"
    ])
    if need_phase4:
        status = run_step("phase4e_panels", phase4_cinematography, project_dir, model=args.model, resume=args.resume)
        if status == "waiting_gate":
            resolved = process_gate(project_dir, "Gate 2", "viewer.html", confirm=args.confirm)
            if resolved == "await_detail":
                print("⏸ 等待分镜修改指令")
                return
    else:
        print("⏭ 跳过 Phase 4（已完成且已审核）")

    if not should_skip_step(project_dir, "phase5_output", args.resume, verbose=True):
        run_step("phase5_output", phase5_output, project_dir)
    else:
        print("⏭ 跳过 Phase 5 Output")

    state = load_run_state(project_dir)
    state["overall_status"] = "completed"
    state["current_step"] = "phase5_output"
    save_run_state(project_dir, state)
    print_run_state_summary(project_dir)
    print("🎉 全流程完成!")


def run_single_phase(args, project_dir, should_skip_step, run_step, phase0_intent_capture, phase1_story_dna, phase2_beats, phase3_characters, phase4_cinematography, phase5_output, phase_lookdev):
    phase_map = {
        "0": ("phase0_input", lambda p, model=None: phase0_intent_capture(p, args.story)),
        "1": ("phase1_story_dna", phase1_story_dna),
        "2": ("phase2_beats", phase2_beats),
        "3": ("phase3_characters", phase3_characters),
        "4": ("phase4e_panels", phase4_cinematography),
        "5": ("phase5_output", lambda p, model=None: phase5_output(p)),
        "lookdev": ("phase4a_lookdev", phase_lookdev),
    }
    step_key, fn = phase_map[args.phase]
    if should_skip_step(project_dir, step_key, args.resume, verbose=True):
        print(f"⏭ 跳过 {step_key}")
        return
    if args.phase in ("0", "5"):
        run_step(step_key, fn, project_dir)
    else:
        extra = {"resume": args.resume} if args.phase == "4" else {}
        run_step(step_key, fn, project_dir, model=args.model, **extra)
