import argparse

from packages.graph.workflow import run_sync


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 1 graph synchronously with MemorySaver"
    )
    parser.add_argument("topic", help="Topic to generate a draft for")
    args = parser.parse_args()

    result = run_sync(args.topic)

    print("Phase 1 Sync Run Result")
    print(f"job_id: {result['job_id']}")
    print(f"status: {result['status']}")
    print(f"revision_count: {result['revision_count']}")
    print(f"is_approved: {result['is_approved']}")
    print(f"draft_preview: {result['draft'][:160]}")
    if result["error_message"]:
        print(f"error: {result['error_message']}")


if __name__ == "__main__":
    main()
