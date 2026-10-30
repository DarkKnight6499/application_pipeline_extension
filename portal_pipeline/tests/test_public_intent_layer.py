"""Author: Yazad Madan. Intent layer: question wording from real portals maps to one stable intent."""
import unittest

import answer_memory
import intent_layer

CASES = [
    ("Have you been previously employed by Regions or any of its divisions, subsidiaries, or affiliates?*", "prev_worked_here"),
    ("Have you previously worked at BBH as a permanent, temporary, intern, co-op, fixed term employee or contingent worker? If you are a current employee, please apply through the Internal Workday Career site.", "prev_worked_here"),
    ("Have you ever worked at Key (as an employee, intern, or contractor) either directly or as part of an acquisition?*", "prev_worked_here"),
    ("Are you currently working at Key (as an employee, intern, or contractor)?*", "current_employee_here"),
    ("Are you related to any current employee of Regions?*", "related_to_employee"),
    ("Do you currently require Regions' sponsorship or need assistance to work legally in the United States? This includes H-1B visas, TN visas, E-3 visas.*", "sponsorship_h1b_only"),
    ("Will you now or in the future require sponsorship (e.g., H-1B visa) by our company to attain or maintain your employment eligibility?*", "sponsorship_h1b_only"),
    ("Will you now or in the future require immigration sponsorship, which includes CPT and STEM OPT?", "sponsorship_opt_listed"),
    ("Have you signed any agreement with a current or prior employer that contains non-solicitation or non-competition restrictions?", "non_compete"),
    ("Are you subject to any restrictions in the scope of your contemplated employment activities?", "non_compete"),
    ("Do you currently hold any financial services licenses? For example: a FINRA Series 63", "financial_license"),
    ("Have you ever been discharged, asked to resign, or resigned to avoid termination from any former employment?*", "discharged_or_resigned"),
    ("Select yes if you: (1) are under investigation by your current employer for alleged violation of any company policies", "under_investigation"),
    ("Are you at least 18 years of age or are you able to submit a work authorization permit?*", "age_18"),
    ("Are you legally authorized to work in the United States?*", "work_authorized_us"),
    ("Are you eligible to work in the United States?*", "work_authorized_us"),
    ("As part of our hiring practices, KeyBank may use Artificial Intelligence (AI) tools provided by a trusted third-party vendor", "ai_tools_consent"),
    ("If you are not selected for this position, KeyBank may wish to consider your application for additional opportunities.", "other_opportunities"),
    ("Please indicate your Veteran status.*", "veteran_status"),
    ("Please indicate if you are Hispanic or Latino.", "hispanic_latino"),
    ("Ethnicity/Race: Choose the category that best applies to you", "ethnicity"),
    ("Please indicate your gender.*", "gender"),
    ("Do you currently participate in an outside activity (i.e. part time job, serving on a board)", "outside_activity"),
    ("Are you willing to travel?*", "willing_travel"),
    ("Are you a California resident?*", "california_resident"),
    ("Please indicate the type of sponsorship that you will need (e.g., H-1B visa or other nonimmigrant sponsorship)", "sponsorship_type_text"),
    ("Please indicate what type of visa you are currently on, if applicable (e.g., F-1 visa).", "current_visa_type"),
    ("What amount of time are you willing to travel?*", "willing_travel"),
]


class IntentLayerTests(unittest.TestCase):
    def test_real_portal_wording_maps_to_expected_intent(self):
        for label, expected in CASES:
            self.assertEqual(intent_layer.classify(label), expected, label)

    def test_unrelated_question_has_no_intent(self):
        self.assertIsNone(intent_layer.classify("What is your favorite color?"))

    def test_learn_then_lookup_serves_a_different_company(self):
        memory = {"answers": {}}
        intent_layer.learn(memory, "Have you been previously employed by Regions or any of its divisions?*", "No")
        self.assertEqual(intent_layer.lookup(memory, "Have you ever worked at Key (as an employee, intern, or contractor)?"), intent_layer.NO)

    def test_yes_and_no_expand_to_portal_wording(self):
        self.assertIn("Opt In", intent_layer.expand(intent_layer.YES))
        self.assertIn("Opt Out", intent_layer.expand(intent_layer.NO))
        self.assertEqual(intent_layer.expand("Master"), ["Master"])

    def test_opt_wording_and_h1b_wording_never_share_an_answer(self):
        memory = {"answers": {}}
        intent_layer.learn(memory, "Do you require sponsorship, including CPT or STEM OPT?", "Yes")
        self.assertIsNone(intent_layer.lookup(memory, "Will you require sponsorship such as an H-1B visa?"))


if __name__ == "__main__":
    unittest.main()
