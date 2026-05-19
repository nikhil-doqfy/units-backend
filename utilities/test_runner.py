import os
import unittest
import pandas as pd

from datetime import datetime

from django.test.runner import DiscoverRunner

from HtmlTestRunner import HTMLTestRunner
from HtmlTestRunner.result import HtmlTestResult
# ============================================================================
# FIX FOR HtmlTestRunner Bug
# Prevents:
# AttributeError:
# 'HtmlTestResult' object has no attribute '_count_relevant_tb_levels'
# ============================================================================

if not hasattr(HtmlTestResult, "_count_relevant_tb_levels"):

    def _count_relevant_tb_levels(self, tb):

        length = 0

        while tb:
            length += 1
            tb = tb.tb_next

        return length

    HtmlTestResult._count_relevant_tb_levels = (
        _count_relevant_tb_levels
    )

# CUSTOM RESULT CLASS FOR EXCEL REPORT

class ExcelTestResult(unittest.TextTestResult):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.rows = []

    def addSuccess(self, test):
        super().addSuccess(test)

        self.rows.append({
            "Test Name": test._testMethodName,
            "Description": (
                test.shortDescription()
                or test._testMethodName
            ),
            "Status": "PASS"
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)

        self.rows.append({
            "Test Name": test._testMethodName,
            "Description": (
                test.shortDescription()
                or test._testMethodName
            ),
            "Status": "FAIL"
        })

    def addError(self, test, err):
        super().addError(test, err)

        self.rows.append({
            "Test Name": test._testMethodName,
            "Description": (
                test.shortDescription()
                or test._testMethodName
            ),
            "Status": "ERROR"
        })

    def addSkip(self, test, reason):
        super().addSkip(test, reason)

        self.rows.append({
            "Test Name": test._testMethodName,
            "Description": (
                test.shortDescription()
                or test._testMethodName
            ),
            "Status": "SKIPPED"
        })

# CUSTOM DJANGO TEST RUNNER
class CustomHTMLAndExcelRunner(DiscoverRunner):

    def run_suite(self, suite, **kwargs):

        os.makedirs("reports", exist_ok=True)
        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )

        # STEP 1 — RUN TESTS FOR EXCEL REPORT

        excel_runner = unittest.TextTestRunner(
            verbosity=2,
            resultclass=ExcelTestResult
        )

        result = excel_runner.run(suite)

        # STEP 2 — GENERATE EXCEL REPORT
        try:

            excel_file = (
                f"reports/test_report_{timestamp}.xlsx"
            )

            df = pd.DataFrame(result.rows)
            total = len(result.rows)
            passed = sum(
                1 for r in result.rows
                if r["Status"] == "PASS"
            )

            failed = sum(
                1 for r in result.rows
                if r["Status"] == "FAIL"
            )

            errors = sum(
                1 for r in result.rows
                if r["Status"] == "ERROR"
            )

            skipped = sum(
                1 for r in result.rows
                if r["Status"] == "SKIPPED"
            )

            summary = pd.DataFrame([{
                "Test Name": "SUMMARY",
                "Description": (
                    f"Total={total}, "
                    f"Pass={passed}, "
                    f"Fail={failed}, "
                    f"Error={errors}, "
                    f"Skipped={skipped}"
                ),
                "Status": f"{passed}/{total} PASSED"
            }])

            df = pd.concat(
                [df, summary],
                ignore_index=True
            )

            with pd.ExcelWriter(
                excel_file,
                engine="openpyxl"
            ) as writer:

                df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Test Results"
                )
                worksheet = writer.sheets[
                    "Test Results"
                ]

                # Auto width
                for col in worksheet.columns:

                    max_length = max(
                        len(str(cell.value or ""))
                        for cell in col
                    )

                    worksheet.column_dimensions[
                        col[0].column_letter
                    ].width = min(max_length + 5, 80)

            print(
                f"\nExcel report generated:"
                f" {excel_file}"
            )

        except Exception as e:

            print(
                f"\nExcel report generation failed:"
                f" {e}"
            )

        # STEP 3 — GENERATE HTML REPORT
        try:

            # IMPORTANT:
            # Build fresh suite for HTML report
            # otherwise suite gets consumed
            new_suite = self.build_suite(
                test_labels=None
            )

            HTMLTestRunner(
                combine_reports=True,
                output="reports",
                report_name=(
                    f"html_report_{timestamp}"
                ),
                verbosity=2,
                descriptions=True,
            ).run(new_suite)

            print(
                f"\nHTML report generated:"
                f" reports/html_report_{timestamp}.html"
            )

        except Exception as e:

            print(
                f"\nHTML report generation failed:"
                f" {e}"
            )
        return result