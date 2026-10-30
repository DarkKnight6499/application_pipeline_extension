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
    ("How Did You Hear About Us?*", "how_did_you_hear"),
    ("Source of your application", "how_did_you_hear"),
]


SPONSORSHIP_CORPUS_BASELINE = [
    ('Are you at least 18 years of age or are you able to submit a work authorization permit?', 'age_18'),
    ('Are you authorized to work on an EAD?', None),
    ('Are you on STEM OPT?', None),
    ('Do you currently require Morgan Stanley to sponsor a work visa on your behalf to commence employment?', 'sponsorship_h1b_only'),
    ("Do you currently require Regions' sponsorship or need assistance to work legally in the United States? This includes H-1B visas, TN visas, E-3 visas.", 'sponsorship_h1b_only'),
    ('Do you hold F-1 status with OPT work authorization?', None),
    ('Do you need immigration support to work for us?', None),
    ('Do you require H1B sponsorship?', 'sponsorship_h1b_only'),
    ('Do you require employer sponsorship for a work permit?', 'sponsorship_h1b_only'),
    ('Do you require immigration sponsorship by our company to attain or maintain your employment eligibility? This includes, for example: H-1B, E-3, TN, O-1, CPT, STEM OPT, or any immigration work authorization requiring a written submission from the company to a government agency or otherwise requiring the entry of the company as your immigration employer of record in government records.', 'sponsorship_opt_listed'),
    ('Do you require sponsorship for OPT?', 'sponsorship_opt_listed'),
    ('Do you require visa sponsorship?', 'sponsorship_h1b_only'),
    ('If you currently hold OPT, are you eligible for a 24-month extension?', None),
    ('Please indicate the type of sponsorship that you will need (e.g., H-1B visa or other nonimmigrant sponsorship)', 'sponsorship_type_text'),
    ('Please indicate what type of visa you are currently on, if applicable (e.g., F-1 visa).', 'current_visa_type'),
    ('Who is your referral sponsor at the company?', None),
    ('Will you in the future require immigration sponsorship by our company to attain or maintain your employment eligibility? This includes, for example: H-1B, E-3, TN, O-1, CPT, STEM OPT, or any immigration work authorization requiring a written submission from the company to a government agency or otherwise requiring the entry of the company as your immigration employer of record in government records.', 'sponsorship_opt_listed'),
    ('Will you in the future require sponsorship for employment visa status?', 'sponsorship_h1b_only'),
    ('Will you now or in the future require immigration sponsorship, which includes CPT and STEM OPT?', 'sponsorship_opt_listed'),
    ('Will you now or in the future require sponsorship (e.g., H-1B visa) by our company to attain or maintain your employment eligibility?', 'sponsorship_h1b_only'),
    ('Will you now or in the future require sponsorship for employment visa status (e.g. H-1B)?', 'sponsorship_h1b_only'),
    ('Will you require H-1B or OPT sponsorship?', 'sponsorship_opt_listed'),
    ('Will you require sponsorship beyond your EAD or OPT?', 'sponsorship_opt_listed'),
    ('Will you require sponsorship in the future to maintain authorization to work in the United States?', 'sponsorship_h1b_only'),
    ('Will you require sponsorship to work in the United States now or in the future?', 'sponsorship_h1b_only'),
    ('Would you like to opt out of marketing communications?', None),
]

NEW_INTENT_CASES = [
    ('salary_expectation', 'What are your salary expectations?', 'What was your previous salary?'),
    ('job_board_source', 'If Internet Job Board, please specify:', 'Which Internet Job Board do you recommend?'),
    ('current_student', 'Are you currently a student?', 'Are you currently a student advisor?'),
    ('available_start_date', 'What is your available start date?', 'What was your employment start date?'),
    ('language_preference', 'What is your preferred language?', 'What programming language do you prefer?'),
    ('essential_functions', 'Can you perform the essential functions of this job with or without reasonable accommodation?', 'Describe the essential functions of your previous job.'),
    ('basic_qualifications', 'Do you meet the basic qualifications for this position?', 'Describe the basic qualifications for this position.'),
    ('preferred_qualifications', 'Do you meet the preferred qualifications for this position?', 'Which preferred qualifications would you like to develop?'),
    ('identity_verification', 'Can you provide proof of identity upon hire?', 'Upload proof of identity to sign in.'),
    ('military_spouse', 'Are you a military spouse?', 'Are you employed as a military spouse counselor?'),
    ('military_reserve', 'Are you a member of the National Guard or Reserves?', 'Do you manage capital reserves?'),
    ('sms_consent', 'Opt in to text messages', 'What is your text message history?'),
    ('protected_veteran', 'Are you a protected Veteran?', 'Are you protected by a collective bargaining agreement?'),
    ('employee_referral', 'Were you referred by an employee?', 'Were you referred by an employment agency?'),
    ('work_type', 'What type of employment are you seeking (full time or part time)?', 'What type of employment did you hold previously?'),
    ('politically_exposed', 'Are you a politically exposed person?', 'Describe your experience with politically exposed clients.'),
    ('securities_registration', 'Are you currently, were you previously, or have you ever attempted to become, registered in the securities industry?', 'Are you interested in the securities industry?'),
    ('middle_name', 'Middle Name', 'Middle school name'),
    ('name_suffix', 'Suffix', 'File suffix'),
    ('address_line2', 'Address Line 2', 'Address Line 20'),
    ('phone_extension', 'Phone Extension', 'Browser extension'),
    ('country', 'Country', 'Which country issued your visa?'),
    ('country_phone_code', 'Country Phone Code', 'Country tax code'),
    ('notice_period', 'Notice period', 'Privacy notice'),
    ('email', 'Email Address', 'Email verification code'),
    ('linkedin_url', 'Please share your LinkedIn url.', 'Which LinkedIn courses have you taken?'),
]


class IntentLayerTests(unittest.TestCase):
    def test_real_portal_wording_maps_to_expected_intent(self):
        for label, expected in CASES:
            self.assertEqual(intent_layer.classify(label), expected, label)

    def test_new_intents_and_near_misses(self):
        for intent, label, near_miss in NEW_INTENT_CASES:
            with self.subTest(intent=intent):
                self.assertEqual(intent_layer.classify(label), intent)
                self.assertIsNone(intent_layer.classify(near_miss))

    def test_sponsorship_corpus_keeps_original_classifications(self):
        for label, expected in SPONSORSHIP_CORPUS_BASELINE:
            with self.subTest(label=label):
                self.assertEqual(intent_layer.classify(label), expected)
                self.assertEqual(intent_layer.classify(label + "*"), expected)

    def test_ambiguous_sponsorship_labels_remain_unclassified(self):
        for label in ("Sponsorship", "Sponsorship eligibility details", "Immigration status"):
            with self.subTest(label=label):
                self.assertIsNone(intent_layer.classify(label))

    def test_repeating_wording_variants(self):
        cases = [
            ("Have you worked for Example Company?", "prev_worked_here"),
            ("Do you have relatives employed by our company?", "related_to_employee"),
            ("Do you have a second job?", "outside_activity"),
            ("Are you 18 or older?", "age_18"),
            ("Are you over 18?", "age_18"),
            ("Available date", "available_start_date"),
            ("Are you open to relocating?", "willing_relocate"),
            ("Do you opt in to AI review of your application?", "ai_tools_consent"),
            ("Are you seeking full-time work?", "work_type"),
        ]
        for label, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(intent_layer.classify(label), expected)

    def test_real_label_gaps_from_answer_memory(self):
        cases = [
            ("State/Province", "state"), ("County", "county"), ("Address", "address_line1"),
            ("Preferred First Name", "preferred_first_name"), ("Military Status", "military_status"),
            ("Military Spouse/Domestic Partner", "military_spouse"),
            ("Are you currently a member of the U.S. National Guard or Reserves?", "military_reserve"),
            ("Please indicate your language preference for receiving communications:", "language_preference"),
            ("To the best of your knowledge, are you a referral of a current Senior Commercial Person (SCP)?", "employee_referral"),
            ("Visa may use automated tools such as AI to support review of your application", "ai_tools_consent"),
            ("Are you legally eligible to work in the country in which this job is located?", "work_authorized_us"),
            ("Do any of your immediate family members work for the company?", "related_to_employee"),
        ]
        for label, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(intent_layer.classify(label), expected)
        self.assertIsNone(intent_layer.classify("State your favorite color"))

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

    def test_alternatives_expand_yes_no_and_keep_rank_rules(self):
        self.assertEqual(intent_layer.expand("Yes|highest"), intent_layer.YES_WORDS + ["highest"])
        self.assertEqual(intent_layer.expand(["NO", "lowest"]), intent_layer.NO_WORDS + ["lowest"])
        self.assertEqual(intent_layer.expand(" First | | Second "), ["First", "Second"])
        self.assertEqual(intent_layer.expand(None), [])

    def test_travel_rule_is_stored_only_in_supplied_memory(self):
        for answer in ("YES|highest", ["YES", "highest"]):
            memory = {"answers": {}}
            self.assertEqual(intent_layer.learn(memory, "Are you willing to travel?", answer), "willing_travel")
            self.assertEqual(intent_layer.lookup(memory, "What amount of time are you willing to travel?"), "YES|highest")
        self.assertIsNone(intent_layer.lookup({"answers": {}}, "Are you willing to travel?"))

    def test_veteran_alternatives_round_trip(self):
        memory = {"answers": {}}
        answer = "I am not a Veteran|I am not a protected veteran"
        intent_layer.learn(memory, "Veteran status", answer)
        self.assertEqual(intent_layer.expand(intent_layer.lookup(memory, "Are you a veteran?")), answer.split("|"))

    def test_source_answer_serves_alternative_question_wording(self):
        memory = {"answers": {}}
        intent_layer.learn(memory, "How Did You Hear About Us?", "Company Website")
        self.assertEqual(intent_layer.lookup(memory, "Source of your application"), "Company Website")


if __name__ == "__main__":
    unittest.main()
