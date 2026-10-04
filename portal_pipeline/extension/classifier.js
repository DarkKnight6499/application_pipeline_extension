/* Shared label classification and honest option matching; ideas from GodsScion/Auto_job_applier_linkedIn (MIT), written fresh. */
(() => {
  if (globalThis.PortalClassifier) return;
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // Lowercase, collapse whitespace, drop punctuation except + and # and a hyphen between letters.
  const normalizeLabel = value => String(value ?? "").toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9+#\s-]+/g, " ")
    .replace(/(?<![a-z])-|-(?![a-z])/g, " ").replace(/\s+/g, " ").trim();
  // Intent and alias text treats a hyphen as a space too.
  const plain = value => normalizeLabel(value).replace(/-/g, " ").replace(/\s+/g, " ").trim();
  const answerKey = value => String(value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
  const phrasePattern = phrase => new RegExp(`(?<![a-z0-9])${escape(normalizeLabel(phrase))}(?![a-z0-9])`);

  function labelHas(text, phrases) {
    const normal = normalizeLabel(text);
    return (phrases || []).some(phrase => phrasePattern(phrase).test(normal));
  }

  function findBadWord(text, words) {
    const normal = normalizeLabel(text);
    return (words || []).find(word => phrasePattern(word).test(normal)) ?? null;
  }

  // "State" inside "United States" must never read as a state-of-residence question.
  function withoutCountryNames(text) {
    return plain(text).replace(/\b(united states of america|united states|u s a|u s|usa|us)\b/g, " ").replace(/\s+/g, " ");
  }

  const PLACE_TERMS = /\b(location s|stated location|selected|country where|country in which|in which you are applying|where this (role|job|position)|position is located|current location)\b/;
  const STATE_WITH_PLACE = /\b(state|province)\b.*\b(where|in which|reside|live|work|applying|located)\b|\b(where|in which)\b.*\b(state|province)\b/;

  // Wording that depends on where the role is, so no single stored answer is honest.
  function placeDependent(text) {
    const copy = withoutCountryNames(text);
    return PLACE_TERMS.test(copy) || STATE_WITH_PLACE.test(copy);
  }

  const COUNTRY_STYLE = ["country of citizenship", "citizenship country", "country of nationality", "nationality"];

  const US_RAW = /(?<![A-Za-z])(?:US|USA|U\.S\.A?\.?|[Uu]nited [Ss]tates)(?![A-Za-z])/;
  const OTHER_PLACES = /\b(united kingdom|uk|u k|great britain|england|canada|india|europe|european union|eu|germany|france|ireland|australia|singapore|hong kong|japan|china|mexico|brazil|emea|apac)\b/;
  const NEGATION_WORDS = /\b(without|no need|unless|if|not|never|cannot|cant|wont|dont|doesnt)\b/;
  const HOLDS_VISA = /\b(currently on|are you on|you on|on an?|hold|holds|holder of|have an?|possess)\b.{0,30}\bvisa\b/;

  // Order matters: negation, place, held-visa status, sponsorship, then citizenship and status words, then authorization.
  // When in doubt the answer is null so the field stays pending.
  function workAuthIntent(text) {
    const t = plain(text);
    if (NEGATION_WORDS.test(t)) return null;
    if (placeDependent(text)) return null;
    if (HOLDS_VISA.test(t)) return "status_question";
    const sponsor = /\b(sponsor|sponsorship|sponsored|visa|immigration support|work permit)\b/.test(t);
    const needs = /\b(require|requires|need|needs|needing)\b/.test(t);
    if (sponsor && needs) {
      const now = /\b(now|currently|at present)\b/.test(t), future = /\b(future|ever|any point|going forward)\b/.test(t);
      return now && future ? "sponsorship_now_or_future" : future ? "sponsorship_future" : now ? "sponsorship_now" : null;
    }
    if (/\b(citizen|citizenship|nationality|green card|permanent resident)\b/.test(t)) return COUNTRY_STYLE.includes(t) ? "citizenship" : "status_question";
    if (/\b(immigration status|visa status|current status)\b/.test(t)) return "status_question";
    // Case-sensitive on the raw label so the pronoun "us" is never read as the country.
    if (!sponsor && !needs && US_RAW.test(String(text ?? "")) && !OTHER_PLACES.test(t)
      && /\b(authori[sz]ed to (lawfully |legally )?work|eligible to work|work authori[sz]ed to work)\b/.test(t)) return "authorized_us";
    return null;
  }

  const CONTACT_ALIASES = {
    first_name: ["first name", "legal first name", "given name"],
    last_name: ["last name", "legal last name", "family name", "surname"],
    full_name: ["full name", "legal name"], email: ["email", "email address", "e mail"],
    phone: ["phone", "phone number", "mobile phone", "telephone"],
    linkedin: ["linkedin", "linkedin profile", "linkedin url"], github: ["github", "github url", "github profile"],
    city: ["city", "city of residence"], location: ["current location", "location of residence"],
    authorized_us: ["are you authorized to work in the us", "are you legally authorized to work in the united states", "are you authorized to work in the united states"],
    sponsorship_now: ["do you require sponsorship now", "do you currently require sponsorship", "do you require visa sponsorship now"],
    sponsorship_future: ["will you require sponsorship in the future", "will you require visa sponsorship in the future", "do you require sponsorship in the future"],
    citizenship: ["country of citizenship", "citizenship country", "nationality"],
    visa_type: ["visa type"], relocation: ["are you willing to relocate", "open to relocation"],
    salary: ["salary expectation", "salary expectations", "compensation expectation"],
    available_from: ["available from", "earliest start date", "when are you available to start"],
    job_source: ["how did you hear about this job", "how did you hear about us", "job source"]
  };
  const HISTORY_ALIASES = {
    employment: {
      "employment.company": ["employer", "employer name", "company", "company name"],
      "employment.title": ["job title", "role title", "position title"],
      "employment.start_date": ["start date", "from date"], "employment.end_date": ["end date", "to date"],
      "employment.start_month": ["start month", "from month"], "employment.start_year": ["start year", "from year"],
      "employment.end_month": ["end month", "to month"], "employment.end_year": ["end year", "to year"],
      "employment.description": ["job description", "responsibilities", "role description"],
      "employment.location": ["location", "employment location"]
    },
    education: {
      "education.school": ["school", "school name", "university", "institution"],
      "education.degree": ["degree", "degree earned"], "education.end_date": ["end date", "graduation date"],
      "education.start_date": ["start date", "from date"], "education.location": ["location", "education location"],
      "education.start_month": ["start month", "from month"], "education.start_year": ["start year", "from year"],
      "education.end_month": ["end month", "graduation month", "to month"], "education.end_year": ["end year", "graduation year", "to year"]
    }
  };
  const PROFILE_INTENTS = new Set(["sponsorship_now", "sponsorship_future", "sponsorship_now_or_future", "authorized_us", "citizenship"]);

  // Status questions have no profile key: they stay pending for a human.
  function classify(label, identity, section) {
    const text = plain(label);
    const history = HISTORY_ALIASES[section];
    if (history) {
      for (const [key, labels] of Object.entries(history)) if (labels.includes(text)) return key;
      return null;
    }
    for (const [key, labels] of Object.entries(CONTACT_ALIASES)) if (labels.includes(text)) return key;
    const intent = workAuthIntent(label);
    return PROFILE_INTENTS.has(intent) ? intent : null;
  }

  const NEGATIONS = ["not", "no", "dont", "do not", "will not", "wont", "never", "unable", "cannot", "cant", "doesnt", "does not"];

  // Exact label or value first; otherwise only a Yes or No answer may use the polarity rules; two survivors return null.
  function matchOption(options, answer) {
    const wanted = answerKey(answer);
    if (!wanted) return null;
    const usable = (options || []).filter(option => !option.disabled);
    const exact = usable.filter(option => answerKey(option.label) === wanted || answerKey(option.value) === wanted);
    if (exact.length === 1) return exact[0];
    if (wanted !== "yes" && wanted !== "no") return null;
    const yes = wanted === "yes", opposite = yes ? "no" : "yes";
    const survivors = usable.filter(option => {
      const label = plain(option.label), first = label.split(" ")[0];
      if (!(first === wanted || label === (yes ? "true" : "false"))) return false;
      return yes ? !findBadWord(label, NEGATIONS) : !phrasePattern(opposite).test(label);
    });
    return survivors.length === 1 ? survivors[0] : null;
  }

  const ATTESTATION_WORDS = ["attest", "certify", "certification", "consent", "agree", "acknowledge", "acknowledgement", "acknowledgment", "declare",
    "declaration", "terms", "privacy policy", "authorize", "i understand", "i confirm", "true and complete", "true and accurate", "signature"];

  // Attestations are never ticked by the helper; an unchecked required box with no profile key is treated the same way.
  function isAttestationCheckbox(field) {
    if (!field || field.type !== "checkbox") return false;
    if (labelHas(field.label, ATTESTATION_WORDS)) return true;
    return !!field.required && !field.checked && !field.key;
  }

  globalThis.PortalClassifier = {labelHas, findBadWord, classify, workAuthIntent, matchOption, isAttestationCheckbox, placeDependent};
})();
