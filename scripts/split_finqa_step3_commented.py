import argparse  # Imports tools for optional command-line settings.
import csv  # Imports tools for reading the report-group CSV file.
import io  # Imports tools for decoding text inside the ZIP file.
import json  # Imports tools for reading and writing JSON files.
import random  # Imports the seeded randomizer used for a repeatable split.
import zipfile  # Imports tools for reading files directly from the ZIP archive.
from pathlib import Path  # Imports a simple cross-platform way to work with file paths.


DEFAULT_SEED = 8694  # Sets the saved random seed for the split.
DEVELOPMENT_RATIO = 0.80  # Sets the development-set target to 80 percent of tasks.
TASKS_MEMBER = "finqa_training/train_tasks.json"  # Names the task-data file inside the ZIP.
GROUPS_MEMBER = "finqa_training/FinQA_Training_Report_Groups.csv"  # Names the report-group CSV inside the ZIP.
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent  # Identifies the repository folder when this file is stored in scripts/.
DEFAULT_ZIP_PATH = REPOSITORY_ROOT / "data/raw/finqa_dataset.zip"  # Sets the normal source-data ZIP location inside the repository.
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "data/splits"  # Sets the normal split-output folder inside the repository.


def parse_arguments():  # Defines the optional settings a user can provide when running the script.
    parser = argparse.ArgumentParser(description="Create a group-safe FinQA development and holdout split.")  # Creates the command-line parser.
    parser.add_argument("--zip", default=str(DEFAULT_ZIP_PATH), help="Path to the FinQA dataset ZIP file.")  # Adds the ZIP-file setting with the repository data path as its default.
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Folder where split files will be saved.")  # Adds the output-folder setting.
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed recorded in the split manifest.")  # Adds the repeatable-randomization setting.
    return parser.parse_args()  # Returns the chosen or default settings.


def main():  # Defines the main Step 3 workflow.
    args = parse_arguments()  # Reads the ZIP path, output folder, and seed settings.
    zip_path = Path(args.zip)  # Converts the ZIP-file name into a file-path object.
    output_dir = Path(args.output_dir)  # Converts the output-folder name into a folder-path object.

    if not zip_path.is_file():  # Checks that the ZIP file exists before trying to read it.
        raise FileNotFoundError(f"Dataset ZIP not found: {zip_path}")  # Stops with a clear message if the ZIP file is missing.

    output_dir.mkdir(parents=True, exist_ok=True)  # Creates the output folder if it does not already exist.

    # Step 1: Load only the task file and report-group file; train_gold.json is not opened.
    with zipfile.ZipFile(zip_path) as archive:  # Opens the dataset ZIP without extracting it manually.
        archive_members = set(archive.namelist())  # Collects the names of all files inside the ZIP.
        required_members = {TASKS_MEMBER, GROUPS_MEMBER}  # Lists the two files required for the split.
        missing_members = required_members - archive_members  # Identifies any required files missing from the ZIP.

        if missing_members:  # Checks whether either required file is missing.
            missing_names = ", ".join(sorted(missing_members))  # Converts missing file names into readable text.
            raise FileNotFoundError(f"Dataset ZIP is missing: {missing_names}")  # Stops if a required split-input file is absent.

        with archive.open(TASKS_MEMBER) as task_file:  # Opens train_tasks.json inside the ZIP.
            tasks = json.load(task_file)  # Loads the FinQA task records into memory.

        with archive.open(GROUPS_MEMBER) as group_file:  # Opens the report-group CSV inside the ZIP.
            csv_text = io.TextIOWrapper(group_file, encoding="utf-8-sig", newline="")  # Decodes the CSV text and removes a possible byte-order mark.
            group_rows = list(csv.DictReader(csv_text))  # Reads each CSV row as a dictionary with named columns.

    # Step 2: Match every task ID to exactly one company-year report group.
    tasks_by_id = {task["task_id"]: task for task in tasks}  # Creates a fast lookup from each task ID to its complete task record.
    task_ids_by_group = {}  # Creates an empty dictionary for report-group task-ID lists.

    for row in group_rows:  # Processes one task-to-report-group CSV row at a time.
        task_id = row["task_id"]  # Reads the task ID from the current CSV row.
        report_group = row["report_group"]  # Reads the company-year report group from the current CSV row.

        if task_id not in tasks_by_id:  # Checks that every CSV task ID has a corresponding task record.
            raise ValueError(f"Task ID in the report-group CSV is missing from train_tasks.json: {task_id}")  # Stops when a CSV task ID has no matching task record.

        task_ids_by_group.setdefault(report_group, []).append(task_id)  # Adds the task ID to its complete company-year report group.

    csv_task_ids = {task_id for group_task_ids in task_ids_by_group.values() for task_id in group_task_ids}  # Collects every task ID represented in the report-group CSV.

    if csv_task_ids != set(tasks_by_id):  # Checks that the CSV and task JSON contain exactly the same task IDs.
        raise ValueError("The report-group CSV task IDs do not exactly match train_tasks.json.")  # Stops when the two source files do not match.

    # Step 3: Set the 80/20 target and randomize report groups with the saved seed.
    development_target = round(len(tasks) * DEVELOPMENT_RATIO)  # Calculates the target number of development tasks.
    report_groups = sorted(task_ids_by_group)  # Sorts report-group names before randomizing them for repeatability.
    random_generator = random.Random(args.seed)  # Creates a randomizer that always uses the saved seed.
    random_generator.shuffle(report_groups)  # Randomizes the full report-group order without splitting groups.

    # Step 4: Assign complete report groups to development or holdout.
    development_groups = []  # Starts an empty list of development report groups.
    holdout_groups = []  # Starts an empty list of holdout report groups.
    development_task_ids = []  # Starts an empty list of development task IDs.
    holdout_task_ids = []  # Starts an empty list of holdout task IDs.

    for report_group in report_groups:  # Processes each complete report group in the randomized order.
        group_task_ids = task_ids_by_group[report_group]  # Retrieves all task IDs belonging to the current report group.

        if len(development_task_ids) + len(group_task_ids) <= development_target:  # Checks whether the complete group fits in the development target.
            development_groups.append(report_group)  # Records the report group as a development group.
            development_task_ids.extend(group_task_ids)  # Adds every task from that report group to development.
        else:  # Handles report groups that do not fit in the development target.
            holdout_groups.append(report_group)  # Records the report group as a holdout group.
            holdout_task_ids.extend(group_task_ids)  # Adds every task from that report group to holdout.

    # Step 5: Create development and holdout task files for later n8n use.
    development_tasks = [tasks_by_id[task_id] for task_id in development_task_ids]  # Collects full task records for development task IDs.
    holdout_tasks = [tasks_by_id[task_id] for task_id in holdout_task_ids]  # Collects full task records for holdout task IDs.

    with (output_dir / "development_tasks.json").open("w", encoding="utf-8") as output_file:  # Opens the development-task output file for writing.
        json.dump(development_tasks, output_file, indent=2)  # Saves development tasks as readable JSON.

    with (output_dir / "holdout_tasks.json").open("w", encoding="utf-8") as output_file:  # Opens the holdout-task output file for writing.
        json.dump(holdout_tasks, output_file, indent=2)  # Saves holdout tasks as readable JSON.

    # Step 6: Validate that tasks and report groups never overlap between the two sets.
    task_overlap = set(development_task_ids) & set(holdout_task_ids)  # Finds task IDs appearing in both splits.
    group_overlap = set(development_groups) & set(holdout_groups)  # Finds report groups appearing in both splits.

    if task_overlap:  # Checks whether any task ID appears in both output files.
        raise ValueError("A task ID appears in both development and holdout.")  # Stops if a task was assigned twice.

    if group_overlap:  # Checks whether any report group appears in both output files.
        raise ValueError("A report group appears in both development and holdout.")  # Stops if a company-year report was split.

    if len(development_task_ids) + len(holdout_task_ids) != len(tasks):  # Checks whether every source task received exactly one assignment.
        raise ValueError("Some tasks were not assigned to a split.")  # Stops if any source task is missing from both outputs.

    # Step 7: Save the split method, seed, task IDs, groups, and counts.
    split_manifest = {  # Starts the reproducibility record for this exact split.
        "split_method": "Sort report groups, shuffle with random.Random(seed), and assign whole report groups to development until the 80 percent task target is reached. Assign remaining report groups to holdout.",  # Records the split procedure.
        "seed": args.seed,  # Records the random seed used for this split.
        "development_ratio_target": DEVELOPMENT_RATIO,  # Records the 80 percent development target.
        "total_tasks": len(tasks),  # Records the total number of source tasks.
        "total_report_groups": len(report_groups),  # Records the total number of source report groups.
        "development_task_count": len(development_task_ids),  # Records the development-task count.
        "holdout_task_count": len(holdout_task_ids),  # Records the holdout-task count.
        "development_report_group_count": len(development_groups),  # Records the development report-group count.
        "holdout_report_group_count": len(holdout_groups),  # Records the holdout report-group count.
        "development_task_ids": development_task_ids,  # Saves the exact development task-ID list.
        "holdout_task_ids": holdout_task_ids,  # Saves the exact holdout task-ID list.
        "development_report_groups": development_groups,  # Saves the exact development report-group list.
        "holdout_report_groups": holdout_groups,  # Saves the exact holdout report-group list.
        "task_overlap_count": len(task_overlap),  # Records the task-ID overlap result.
        "report_group_overlap_count": len(group_overlap),  # Records the report-group overlap result.
    }  # Completes the reproducibility record.

    with (output_dir / "split_manifest.json").open("w", encoding="utf-8") as output_file:  # Opens the split-manifest file for writing.
        json.dump(split_manifest, output_file, indent=2)  # Saves the split method, IDs, groups, and counts as readable JSON.

    print("Step 3 split complete.")  # Prints a completion message.
    print(f"Development tasks: {len(development_task_ids)}")  # Prints the development-task count.
    print(f"Holdout tasks: {len(holdout_task_ids)}")  # Prints the holdout-task count.
    print(f"Development report groups: {len(development_groups)}")  # Prints the development report-group count.
    print(f"Holdout report groups: {len(holdout_groups)}")  # Prints the holdout report-group count.


if __name__ == "__main__":  # Checks that Python is running this file directly.
    main()  # Starts the Step 3 split workflow.
