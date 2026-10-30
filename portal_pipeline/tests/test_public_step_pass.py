"""Author: Yazad Madan. Browser-free regressions for the Workday step pass."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import intent_layer
import step_pass

# Config
TRAVEL_OPTIONS = ["Select One", "None", "Up to 10%", "11%-20%", "91%-100%"]
SALARY_OPTIONS = ["Select One", "Less than 40,000", "40,000 - 50,000", "50,001 and above"]
DATE_VALUE = "2031-04-09"


def collection(items=()):
    result = Mock()
    result.count.return_value = len(items)
    result.nth.side_effect = lambda index: items[index]
    result.first = items[0] if items else Mock()
    result.all_inner_texts.return_value = [item.inner_text() for item in items]
    return result


def field_page(label, selectors):
    field = Mock()
    field.inner_text.return_value = label
    field.get_attribute.return_value = None
    field.locator.side_effect = lambda selector: selectors.get(selector, collection())
    page = Mock()
    page.locator.side_effect = lambda selector: collection([field]) if selector == step_pass.FIELD else collection()
    return page, field


def option_page(names, current="Select One"):
    items = []
    for name in names:
        item = Mock()
        item.inner_text.return_value = name
        items.append(item)
    page, button = Mock(), Mock()
    page.locator.return_value = collection(items)
    button.inner_text.return_value = current
    return page, button, items


class OptionTests(unittest.TestCase):
    def test_alternatives_and_case_insensitive_matching(self):
        names = ["Select One", "I am not a protected veteran"]
        answer = "I am not a Veteran|I AM NOT A PROTECTED VETERAN"
        self.assertEqual(step_pass.choose_option(names, answer), names[1])
        self.assertEqual(step_pass.choose_option(names, answer.split("|")), names[1])
        self.assertTrue(step_pass.answer_matches(names[1].upper(), answer))

    def test_highest_and_lowest_skip_placeholders(self):
        self.assertEqual(step_pass.choose_option(TRAVEL_OPTIONS, "highest"), "91%-100%")
        self.assertEqual(step_pass.choose_option(TRAVEL_OPTIONS, "lowest"), "None")
        self.assertEqual(step_pass.choose_option(TRAVEL_OPTIONS, ["Yes", "highest"]), "91%-100%")
        self.assertEqual(step_pass.choose_option(["Select One", "Yes", "No"], "YES|highest"), "Yes")
        self.assertFalse(step_pass.answer_matches("None", "highest"))

    def test_empty_placeholder_and_ambiguous_options_are_pending(self):
        for names in ([], ["", " SELECT ONE "]):
            for answer in ("highest", "lowest"):
                self.assertIsNone(step_pass.choose_option(names, answer))
        self.assertIsNone(step_pass.choose_option(["Master of Arts", "Master of Science"], "Master"))
        self.assertIsNone(step_pass.choose_option(["No"], "YES"))

    def test_prefix_match_preserved(self):
        self.assertEqual(step_pass.choose_option(["Master's degree"], "Master"), "Master's degree")

    def test_salary_bands_and_boundaries(self):
        cases = [
            ("$120,000-$130,000", "125000", True),
            ("$120,000-$130,000", 120000, True),
            ("$120,000-$130,000", 130000, True),
            ("80,001 - 90,000", 85000, True),
            ("Less than 40,000", 39999, True),
            ("Less than 40,000", 40000, False),
            ("90,000 and above", 90000, True),
            ("90,000 and above", 89999, False),
            ("$40,000.50 - $50,000.75", "45000.25", True),
            ("50,000 - 40,000", 45000, False),
            ("Select One", 45000, False),
            ("Negotiable", 45000, False),
            ("Up to 40,000", 40000, True),
            ("Above 40,000", 40000, False),
            ("Above 40,000", 40001, True),
        ]
        for option, salary, expected in cases:
            with self.subTest(option=option, salary=salary):
                self.assertEqual(step_pass.salary_band_contains(option, salary), expected)

    def test_salary_choice_refuses_missing_ambiguous_or_invalid_bands(self):
        self.assertEqual(step_pass.choose_salary_option(SALARY_OPTIONS, 45000), SALARY_OPTIONS[2])
        self.assertIsNone(step_pass.choose_salary_option(["10 - 20", "20 - 30"], 20))
        for salary in ("invalid", "NaN", "Infinity", -1, None):
            self.assertIsNone(step_pass.choose_salary_option(SALARY_OPTIONS, salary))
        self.assertIsNone(step_pass.choose_salary_option(["10 - 20"], 30))

    def test_compensation_labels(self):
        for label in ("Desired Base Salary*", "minimum total compensation*", "Salary expectation", "Minimum pay"):
            self.assertRegex(label, step_pass.SALARY_LABEL)


class StepPassTests(unittest.TestCase):
    def test_resolve_reads_local_intent_after_company_lookup(self):
        memory = {"answers": {}}
        intent_layer.learn(memory, "Are you willing to travel?", "YES|highest")
        company_kb = SimpleNamespace(find_answer=Mock(return_value=None), Q_ANSWER_COLUMN="answer")
        with patch.dict("sys.modules", {"company_kb": company_kb}):
            answer = step_pass.resolve("Example", memory, "What amount of time are you willing to travel?")
        self.assertEqual(step_pass.choose_option(TRAVEL_OPTIONS, answer), TRAVEL_OPTIONS[-1])
        company_kb.find_answer.assert_called_once()

    def test_picker_clicks_highest_and_salary_band(self):
        for names, wanted, salary, expected in (
            (TRAVEL_OPTIONS, "YES|highest", None, len(TRAVEL_OPTIONS) - 1),
            (SALARY_OPTIONS, None, "45000", 2),
        ):
            with self.subTest(wanted=wanted, salary=salary):
                page, button, items = option_page(names)
                self.assertEqual(step_pass.pick_option(page, button, wanted, salary=salary), (names[expected], names))
                items[expected].click.assert_called_once()
                for index, item in enumerate(items):
                    if index != expected:
                        item.click.assert_not_called()

    def test_picker_closes_without_click_when_correct_or_unmatched(self):
        for answer, current, expected in (("highest", TRAVEL_OPTIONS[-1], TRAVEL_OPTIONS[-1]), ("Missing", "None", None)):
            page, button, items = option_page(TRAVEL_OPTIONS, current=current)
            chosen, _ = step_pass.pick_option(page, button, answer)
            self.assertEqual(chosen, expected)
            for item in items:
                item.click.assert_not_called()
            page.keyboard.press.assert_called_once_with("Escape")

    def test_existing_veteran_alternative_does_not_open_menu(self):
        button = Mock()
        button.inner_text.return_value = "I AM NOT A PROTECTED VETERAN"
        page, _ = field_page("Veteran status*", {step_pass.LISTBOX: collection([button])})
        log = []
        with patch.object(step_pass, "resolve", return_value="I am not a Veteran|I am not a protected veteran"):
            self.assertEqual(step_pass.pass_over_step(page, "Example", {}, log), [])
        button.click.assert_not_called()
        self.assertEqual(log, [])

    def test_travel_rule_comes_from_local_intent_memory(self):
        memory = {"answers": {}}
        intent_layer.learn(memory, "Are you willing to travel?", "YES|highest")
        button = Mock()
        button.inner_text.return_value = "Select One"
        page, _ = field_page("What amount of time are you willing to travel?*", {step_pass.LISTBOX: collection([button])})
        with patch.object(step_pass, "resolve", side_effect=lambda company, data, label: intent_layer.lookup(data, label)), patch.object(step_pass, "pick_option", return_value=("91%-100%", TRAVEL_OPTIONS)) as picker:
            step_pass.pass_over_step(page, "Example", memory, [])
        self.assertEqual(picker.call_args.args[2], "YES|highest")

    def test_salary_dropdown_uses_cli_value(self):
        button = Mock()
        button.inner_text.return_value = "Select One"
        page, _ = field_page("Desired Base Salary*", {step_pass.LISTBOX: collection([button])})
        with patch.object(step_pass, "resolve") as resolver, patch.object(step_pass, "pick_option", return_value=(SALARY_OPTIONS[2], SALARY_OPTIONS)) as picker:
            step_pass.pass_over_step(page, "Example", {}, [], salary="45000")
        resolver.assert_not_called()
        self.assertEqual(picker.call_args.kwargs["salary"], "45000")

    def test_date_types_digits_with_tabs_without_click_or_fill(self):
        parts = {name: Mock() for name in step_pass.DATE_INPUTS}
        for box in parts.values():
            box.input_value.return_value = ""
        page = Mock()
        self.assertTrue(step_pass.fill_date(page, parts, DATE_VALUE))
        self.assertEqual(page.keyboard.type.call_args_list, [call("04"), call("09"), call("2031")])
        self.assertEqual(page.keyboard.press.call_args_list, [call("ControlOrMeta+A"), call("Tab")] * 3)
        parts["month"].focus.assert_called_once()
        for box in parts.values():
            box.click.assert_not_called()
            box.fill.assert_not_called()
            box.scroll_into_view_if_needed.assert_not_called()

    def test_date_already_correct_or_invalid_causes_no_typing(self):
        parts = {name: Mock() for name in step_pass.DATE_INPUTS}
        for name, value in {"month": "4", "day": "09", "year": "2031"}.items():
            parts[name].input_value.return_value = value
        page = Mock()
        self.assertFalse(step_pass.fill_date(page, parts, DATE_VALUE))
        with self.assertRaises(ValueError):
            step_pass.fill_date(page, parts, "2031-02-30")
        page.keyboard.type.assert_not_called()

    def test_month_day_year_date_format(self):
        parts = {name: Mock() for name in step_pass.DATE_INPUTS}
        for box in parts.values():
            box.input_value.return_value = ""
        page = Mock()
        self.assertTrue(step_pass.fill_date(page, parts, "04/09/2031"))
        self.assertEqual(page.keyboard.type.call_args_list, [call("04"), call("09"), call("2031")])

    def test_only_required_dates_are_filled(self):
        for required, current in ((True, ""), (True, "1"), (False, "")):
            with self.subTest(required=required, current=current):
                parts = {name: Mock() for name in step_pass.DATE_INPUTS}
                for box in parts.values():
                    box.input_value.return_value = current
                    box.get_attribute.return_value = None
                selectors = {selector: collection([parts[name]]) for name, selector in step_pass.DATE_INPUTS.items()}
                page, _ = field_page("Available date" + ("*" if required else ""), selectors)
                with patch.object(step_pass, "resolve", return_value=DATE_VALUE):
                    step_pass.pass_over_step(page, "Example", {}, [])
                self.assertEqual(page.keyboard.type.call_count, 3 if required and not current else 0)

    def test_invalid_unknown_and_incomplete_required_dates_stay_pending(self):
        for wanted, complete in ((None, True), ("2031-02-30", True), (DATE_VALUE, False)):
            with self.subTest(wanted=wanted, complete=complete):
                parts = {name: Mock() for name in step_pass.DATE_INPUTS}
                for box in parts.values():
                    box.input_value.return_value = ""
                selectors = {selector: collection([parts[name]]) for name, selector in step_pass.DATE_INPUTS.items() if complete or name != "day"}
                page, _ = field_page("Available date*", selectors)
                with patch.object(step_pass, "resolve", return_value=wanted):
                    self.assertEqual(step_pass.pass_over_step(page, "Example", {}, []), [{"label": "Available date*", "options": []}])
                page.keyboard.type.assert_not_called()

    def test_required_attribute_triggers_date_typing(self):
        parts = {name: Mock() for name in step_pass.DATE_INPUTS}
        for box in parts.values():
            box.input_value.return_value = ""
            box.get_attribute.side_effect = lambda name: "true" if name == "aria-required" else None
        selectors = {selector: collection([parts[name]]) for name, selector in step_pass.DATE_INPUTS.items()}
        page, _ = field_page("Available date", selectors)
        with patch.object(step_pass, "resolve", return_value=DATE_VALUE):
            self.assertEqual(step_pass.pass_over_step(page, "Example", {}, []), [])
        self.assertEqual(page.keyboard.type.call_count, 3)

    def test_date_focus_failure_never_retries_click(self):
        parts = {name: Mock() for name in step_pass.DATE_INPUTS}
        for box in parts.values():
            box.input_value.return_value = ""
        parts["month"].focus.side_effect = RuntimeError("off screen")
        with self.assertRaises(RuntimeError):
            step_pass.fill_date(Mock(), parts, DATE_VALUE)
        parts["month"].focus.assert_called_once()
        parts["month"].click.assert_not_called()

    def test_multiselect_waits_and_clicks_matching_option(self):
        box, option = Mock(), Mock()
        option.inner_text.return_value = "Company Website"
        container = Mock()
        container.locator.side_effect = lambda selector: collection([box]) if selector == "input" else collection()
        page, _ = field_page("How Did You Hear About Us?*", {step_pass.MULTISELECT: collection([container])})
        options = collection([option])
        field_locator = page.locator.side_effect
        page.locator.side_effect = lambda selector: options if selector == step_pass.SEARCH_OPTIONS else field_locator(selector)
        with patch.object(step_pass, "resolve", return_value="Company Website"):
            self.assertEqual(step_pass.pass_over_step(page, "Example", {}, []), [])
        box.fill.assert_called_once_with("Company Website")
        option.wait_for.assert_called_once()
        option.click.assert_called_once()
        page.keyboard.press.assert_not_called()

    def test_multiselect_existing_chip_is_preserved(self):
        box, chip = Mock(), Mock()
        chip.inner_text.return_value = "COMPANY WEBSITE"
        container = Mock()
        container.locator.side_effect = lambda selector: collection([box]) if selector == "input" else collection([chip])
        page, _ = field_page("How Did You Hear About Us?*", {step_pass.MULTISELECT: collection([container])})
        with patch.object(step_pass, "resolve", return_value="Referral|Company Website"):
            step_pass.pass_over_step(page, "Example", {}, [])
        box.fill.assert_not_called()

    def test_multiselect_alternatives_and_no_match(self):
        for names, expected in ((["Second"], "Second"), (["Unrelated"], None)):
            with self.subTest(names=names):
                page, _, items = option_page(names)
                unrelated = Mock()
                unrelated.inner_text.return_value = "Unrelated"
                page.locator.side_effect = [collection([unrelated]), collection(items)]
                box, container = Mock(), Mock()
                container.locator.return_value = collection([box])
                chosen, _ = step_pass.pick_search_option(page, container, "First|Second")
                self.assertEqual(chosen, expected)
                self.assertEqual(box.fill.call_args_list, [call("First"), call("Second")] + ([call("")] if expected is None else []))
                if expected:
                    items[0].click.assert_called_once()
                    page.keyboard.press.assert_not_called()
                else:
                    items[0].click.assert_not_called()
                    page.keyboard.press.assert_called_once_with("Escape")

    def test_multiselect_wait_timeout_does_not_click(self):
        page, _, items = option_page(["Company Website"])
        items[0].wait_for.side_effect = TimeoutError("No options")
        box, container = Mock(), Mock()
        container.locator.return_value = collection([box])
        self.assertEqual(step_pass.pick_search_option(page, container, "Company Website"), (None, []))
        items[0].click.assert_not_called()
        self.assertEqual(box.fill.call_args_list, [call("Company Website"), call("")])


class NavigationTests(unittest.TestCase):
    def test_unreadable_title_never_clicks_next(self):
        for title in ("", "   ", "Review"):
            page = Mock()
            self.assertFalse(step_pass.advance_step(page, title))
            page.locator.assert_not_called()

    def test_submit_wording_never_clicked(self):
        for label in ("Submit", "Review and SUBMIT", "Send Application"):
            page, button = Mock(), Mock()
            page.locator.return_value = collection([button])
            button.inner_text.return_value = label
            button.get_attribute.return_value = None
            self.assertFalse(step_pass.advance_step(page, "Questions"))
            button.click.assert_not_called()

    def test_native_submit_and_accessible_submit_labels_are_blocked(self):
        for attributes in ({"type": "submit"}, {"aria-label": "Submit Application"}):
            page, button = Mock(), Mock()
            page.locator.return_value = collection([button])
            button.inner_text.return_value = "Next"
            button.get_attribute.side_effect = attributes.get
            self.assertFalse(step_pass.advance_step(page, "Questions"))
            button.click.assert_not_called()

    def test_unreadable_button_never_clicked(self):
        page, button = Mock(), Mock()
        page.locator.return_value = collection([button])
        button.inner_text.side_effect = RuntimeError("unreadable")
        self.assertFalse(step_pass.advance_step(page, "Questions"))
        button.click.assert_not_called()

    def test_next_can_advance(self):
        page, button = Mock(), Mock()
        page.locator.return_value = collection([button])
        button.inner_text.return_value = "Save and Continue"
        button.get_attribute.return_value = None
        self.assertTrue(step_pass.advance_step(page, "Questions"))
        button.click.assert_called_once()


if __name__ == "__main__":
    unittest.main()
