"""The five predefined exercises. Each starter program contains ONE classic
beginner bug. `hints` go from gentle to specific and are used when the AI
explanation is unavailable. `solution_markers` are fixes the AI must never
hand over (see explain.guardrail)."""

EXERCISES = [
    {
        "id": "ex1",
        "title": "1. Count to five",
        "goal": "Print the numbers 1 to 5, one per line.",
        "concept": "range(a, b) stops BEFORE b",
        "starter": "for i in range(1, 5):\n    print(i)\n",
        "tests": [{"stdin": "", "expected": "1\n2\n3\n4\n5\n"}],
        "watch": ["i"],
        "hints": [
            "Step through the loop and watch the value of i each time line 2 is about to run.",
            "What is the last value i takes before the loop ends? Is it the last number you wanted?",
            "range(a, b) counts from a up to, but not including, b. Which end value would include 5?",
        ],
        "solution_markers": ["range(1, 6)", "range(1,6)", "range(6)"],
    },
    {
        "id": "ex2",
        "title": "2. Add up the scores",
        "goal": "Add up all the scores in the list and print 'Total: 10'.",
        "concept": "where you set a running total to 0 matters",
        "starter": (
            "scores = [3, 5, 2]\n"
            "for s in scores:\n"
            "    total = 0\n"
            "    total = total + s\n"
            "print(\"Total:\", total)\n"
        ),
        "tests": [{"stdin": "", "expected": "Total: 10\n"}],
        "watch": ["total", "s"],
        "hints": [
            "Watch the value of total at every step. Does it keep growing?",
            "Which line sets total back to 0, and how many times does that line run?",
            "A running total should be set to 0 once. Is line 3 running once, or once per score?",
        ],
        # The fix is "set total to 0 once, before the loop" - block it in words.
        "solution_markers": ["before the loop", "outside the loop", "above the loop", "out of the loop"],
    },
    {
        "id": "ex3",
        "title": "3. Double a number",
        "goal": "double(4) should give back 8, so the program prints 'Result is 8'.",
        "concept": "print shows a value; return gives it back to the caller",
        "starter": (
            "def double(n):\n"
            "    print(n * 2)\n"
            "\n"
            "result = double(4)\n"
            "print(\"Result is\", result)\n"
        ),
        "tests": [{"stdin": "", "expected": "Result is 8\n"}],
        "watch": ["result", "n"],
        "hints": [
            "Find the step where double() finishes. What value does it give back?",
            "Printing a value puts it on the screen. Does that also give it back to the line that called double()?",
            "A function that doesn't use return gives back None. Which keyword sends a value back to the caller?",
        ],
        "solution_markers": ["return n * 2", "return n*2", "return 2 * n", "return 2*n"],
    },
    {
        "id": "ex4",
        "title": "4. Next year's age",
        "goal": "Read an age and print how old the person will be next year.",
        "concept": "input() always gives you text, not a number",
        "starter": (
            "age = input()\n"
            "next_year = age + 1\n"
            "print(\"Next year you will be\", next_year)\n"
        ),
        "tests": [
            {"stdin": "15", "expected": "Next year you will be 16\n"},
            {"stdin": "40", "expected": "Next year you will be 41\n"},
        ],
        "watch": ["age", "next_year"],
        "hints": [
            "Look at the variable panel after line 1. What type is age?",
            "Python can't add the number 1 to a piece of text. What is age: '15' or 15?",
            "You need to turn the text into a whole number before adding to it. Which built-in function does that?",
        ],
        "solution_markers": ["int(age)", "int(input())", "int(input( ))"],
    },
    {
        "id": "ex5",
        "title": "5. Keep a backup",
        "goal": "Add 4 to the backup list only. The original should stay [1, 2, 3].",
        "concept": "assigning a list gives it a second name, not a copy",
        "starter": (
            "original = [1, 2, 3]\n"
            "backup = original\n"
            "backup.append(4)\n"
            "print(\"Original:\", original)\n"
            "print(\"Backup:\", backup)\n"
        ),
        "tests": [{"stdin": "", "expected": "Original: [1, 2, 3]\nBackup: [1, 2, 3, 4]\n"}],
        "watch": ["original", "backup"],
        "hints": [
            "After line 2, look at the variable panel. Do you see a 'same list as' badge?",
            "When line 3 adds 4 to backup, what happens to original at the same moment?",
            "backup = original gives the list a second name. How could you make a separate copy instead?",
        ],
        "solution_markers": ["original.copy()", "list(original)", "original[:]", "copy.copy("],
    },
]

BY_ID = {e["id"]: e for e in EXERCISES}


def public_view(ex: dict) -> dict:
    """What the browser is allowed to see (no hints or solution markers)."""
    return {
        "id": ex["id"],
        "title": ex["title"],
        "goal": ex["goal"],
        "starter": ex["starter"],
        "tests": [{"stdin": t["stdin"], "expected": t["expected"]} for t in ex["tests"]],
    }
