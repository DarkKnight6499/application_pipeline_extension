"""Shared label classifier and honest option matcher, run on blank synthetic pages."""
import json

from browser_test_support import SyntheticBrowserTest
from test_public_greenhouse_select import CLASSIFICATION_CORPUS, PROFILE_VALUES

STATUS_WORDINGS = [
    "What is your current immigration status?",
    "What is your visa status?",
    "Please indicate your current status",
    "Are you a green card holder?",
    "Are you a permanent resident of the United States?",
]


class PublicClassifierTests(SyntheticBrowserTest):
    def call(self, expression, argument=None):
        return self.page.evaluate(f"argument => {expression}", argument)

    def blank(self):
        self.open_markup("<p>blank</p>")

    def test_existing_greenhouse_corpus_still_classifies(self):
        self.blank()
        for label, expected in CLASSIFICATION_CORPUS:
            with self.subTest(label=label):
                self.assertEqual(self.call("PortalClassifier.classify(argument, '', 'contact')", label), expected)
        rows = "".join(f'<label>{label}<select><option></option><option>Yes</option><option>No</option></select></label>' for label, _ in CLASSIFICATION_CORPUS)
        self.open_markup(rows)
        keys = {field["label"]: field["key"] for field in self.scan(PROFILE_VALUES)}
        for label, expected in CLASSIFICATION_CORPUS:
            with self.subTest(engine=label):
                self.assertEqual(keys[label], expected)

    def test_united_states_does_not_trigger_state_branch(self):
        self.blank()
        for label in ("Are you legally authorized to work in the United States?", "Are you authorized to work in the United States of America?",
                      "Are you eligible to work in the U.S.?", "Are you authorized to work in the USA?"):
            with self.subTest(label=label):
                self.assertFalse(self.call("PortalClassifier.placeDependent(argument)", label))
                self.assertEqual(self.call("PortalClassifier.workAuthIntent(argument)", label), "authorized_us")
        for label in ("Are you authorized to work in the state where you will be employed?", "Which province are you applying in?"):
            with self.subTest(label=label):
                self.assertTrue(self.call("PortalClassifier.placeDependent(argument)", label))
                self.assertIsNone(self.call("PortalClassifier.workAuthIntent(argument)", label))

    def test_require_work_authorization_not_inverted(self):
        self.blank()
        for label in ("Do you require work authorization?", "Do you require work authorization in the United States?", "Will you need work authorization in the US?"):
            with self.subTest(label=label):
                self.assertIsNone(self.call("PortalClassifier.workAuthIntent(argument)", label))
                self.assertIsNone(self.call("PortalClassifier.classify(argument, '', 'contact')", label))

    def test_without_sponsorship_returns_null(self):
        self.blank()
        for label in ("Are you authorized to work without sponsorship?", "Can you work in the US with no need for sponsorship?",
                      "Are you authorized to work in the US if you do not need sponsorship?", "Unless sponsored, are you authorized to work in the US?"):
            with self.subTest(label=label):
                self.assertIsNone(self.call("PortalClassifier.workAuthIntent(argument)", label))

    def test_sponsorship_is_checked_before_authorization(self):
        self.blank()
        label = "Will you require sponsorship in the future to maintain authorization to work in the United States?"
        self.assertEqual(self.call("PortalClassifier.workAuthIntent(argument)", label), "sponsorship_future")
        self.assertEqual(self.call("PortalClassifier.workAuthIntent(argument)", "Do you currently require visa sponsorship?"), "sponsorship_now")

    def test_whole_word_matching(self):
        self.blank()
        self.assertTrue(self.call("PortalClassifier.labelHas('Do you require a visa?', ['visa'])"))
        self.assertFalse(self.call("PortalClassifier.labelHas('Provisional supervisor', ['visa', 'sor'])"))
        self.assertEqual(self.call("PortalClassifier.findBadWord('Do you require a visa?', ['sponsor', 'visa'])"), "visa")
        self.assertIsNone(self.call("PortalClassifier.findBadWord('Provisional', ['visa'])"))
        self.assertTrue(self.call("PortalClassifier.labelHas('Experience with C++ and C#', ['c++', 'c#'])"))
        self.assertFalse(self.call("PortalClassifier.labelHas('Experience with C and Java', ['c++'])"))

    def test_citizenship_only_for_country_style_questions(self):
        self.blank()
        self.assertEqual(self.call("PortalClassifier.workAuthIntent(argument)", "Country of citizenship"), "citizenship")
        self.assertEqual(self.call("PortalClassifier.workAuthIntent(argument)", "Are you a U.S. citizen?"), "status_question")

    def test_status_question_detected(self):
        self.blank()
        for label in STATUS_WORDINGS:
            with self.subTest(label=label):
                self.assertEqual(self.call("PortalClassifier.workAuthIntent(argument)", label), "status_question")
                self.assertIsNone(self.call("PortalClassifier.classify(argument, '', 'contact')", label))

    def match(self, options, answer):
        result = self.call("PortalClassifier.matchOption(argument.options, argument.answer)", {"options": [{"label": o, "value": o} for o in options], "answer": answer})
        return result["label"] if result else None

    def test_match_option_yes_variants(self):
        self.blank()
        self.assertEqual(self.match(["Yes, I am authorized", "No, I am not authorized"], "Yes"), "Yes, I am authorized")
        self.assertEqual(self.match(["Yes, I am authorized", "No, I am not authorized"], "No"), "No, I am not authorized")
        self.assertEqual(self.match(["Select", "Yes", "No"], "Yes"), "Yes")
        self.assertEqual(self.match(["True", "False"], "No"), "False")
        for answer in ("Yes",):
            self.assertIsNone(self.match(["No, I am not authorized", "No, I will not need it"], answer))
            self.assertIsNone(self.match(["Yes but I do not qualify", "No"], answer))

    def test_match_option_returns_null_on_two_candidates(self):
        self.blank()
        self.assertIsNone(self.match(["Yes, I am authorized", "Yes, with a visa"], "Yes"))
        self.assertIsNone(self.match(["No, never", "No, not now"], "No"))
        self.assertIsNone(self.match(["Yes", "Yes"], "Yes"))
        self.assertIsNone(self.match(["Maybe", "Perhaps"], "Yes"))
        self.assertIsNone(self.match(["Yes", "No"], ""))

    def test_match_option_no_substring(self):
        self.blank()
        self.assertIsNone(self.match(["Not authorized"], "authorized"))
        self.assertIsNone(self.match(["I am not authorized", "I am authorized to work"], "authorized"))
        self.assertEqual(self.match(["Authorized", "Not authorized"], "authorized"), "Authorized")
        self.assertIsNone(self.match(["Nobody", "Yesterday"], "Yes"))
        self.assertIsNone(self.match(["Nobody", "Yesterday"], "No"))

    def test_match_option_skips_disabled(self):
        self.blank()
        result = self.call("PortalClassifier.matchOption([{label: 'Yes', value: 'y', disabled: true}, {label: 'No', value: 'n'}], 'Yes')")
        self.assertIsNone(result)

    def test_attestation_checkbox_manual_only(self):
        rows = ('<label>I acknowledge that the information above is true<input id="ack" type="checkbox"></label>'
                '<label>Keep me posted<input id="req" type="checkbox" required></label>'
                '<label>Send newsletter<input id="opt" type="checkbox"></label>')
        self.open_markup(rows)
        fields = {field["label"]: field for field in self.scan()}
        self.assertEqual(fields["I acknowledge that the information above is true"]["status"], "manual_only")
        self.assertEqual(fields["Keep me posted"]["status"], "manual_only")
        self.assertNotEqual(fields["Send newsletter"]["status"], "manual_only")
        self.assertTrue(self.call("PortalClassifier.isAttestationCheckbox({type: 'checkbox', label: 'I certify this is correct', key: null, required: false, checked: false})"))
        self.assertFalse(self.call("PortalClassifier.isAttestationCheckbox({type: 'text', label: 'I certify this is correct', key: null, required: true})"))
        self.assertFalse(self.call("PortalClassifier.isAttestationCheckbox({type: 'checkbox', label: 'Open to relocation', key: 'relocation', required: true, checked: false})"))
        self.assertEqual(json.dumps(self.page.evaluate("PortalEngine.inspect().fields.map(f => f.label)")).count("acknowledge"), 0)
