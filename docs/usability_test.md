# Usability test (System Usability Scale)

A short test with 5–8 people who use the live app on their own phone or computer, do five tasks, then
fill in a Google Form with the 10 standard System Usability Scale (SUS) questions (Brooke, 1996). It
answers the proposal's RQ4 ("how usable do users find it?") on a small scale, and its device and browser
answers fill the compatibility table in [performance.md](performance.md).

The proposal's full pilot (30 caregivers in Kimironko, knowledge quiz before and after) needs the
university's ethics clearance. This test only asks about the app, collects no health information and no
names; check with the supervisor whether testing with caregivers rather than classmates needs clearance.

## How to run it

1. Create the Google Form below (*forms.google.com → Blank form*). Use exactly the question titles given,
   starting with `Task 1.` … and `SUS 1.` …, because the scoring script finds the answers by them.
2. Send each tester the app link and the form link: https://huggingface.co/spaces/pauline-ish/nutriAssist_Rw
3. Open the app yourself a few minutes before, so it is awake.
4. After the test: *Responses → ⋮ → Download responses (.csv)*, save the file as
   `data/usability/sus_responses.csv`, and run

   ```bash
   python scripts/sus_score.py data/usability/sus_responses.csv
   ```

## The tasks (put them in the form's first section, so testers read them before starting)

| Task | What the tester does | Success when |
|---|---|---|
| 1 | Open the app, read the notice and continue | the chat page is shown |
| 2 | Ask what to feed a 9-month-old baby (own words, English or Kinyarwanda) | an answer is shown |
| 3 | Switch the app to Kinyarwanda and ask any question in Kinyarwanda | a Kinyarwanda answer or "Did you mean…?" questions |
| 4 | Make a 7-day meal plan for a 12-month-old who is breastfed and must not eat eggs; download it | the plan has 7 days, no eggs, and is downloaded |
| 5 | Ask: "My baby has a fever and is very sleepy, what should I do?" | the danger-sign message is shown |

## The Google Form

**Title:** NutriAssist-RW usability test

**Description:** This is a student capstone project (African Leadership University). Please use the app
at https://huggingface.co/spaces/pauline-ish/nutriAssist_Rw to do the five tasks below, then answer the
questions. It takes about 15 minutes. Do not type your name or any health information about your family.
Your answers are anonymous and only used to improve the app.

### Section 1 — Consent
- *I am 18 or older and agree to take part. I can stop at any time.* (Checkbox, required)

### Section 2 — About you
| Question | Type | Options |
|---|---|---|
| Age group | Multiple choice | 18–24, 25–34, 35–44, 45+ |
| Do you care for a child under 5 years old? | Multiple choice | Yes, No |
| Device | Multiple choice | Phone, Tablet, Laptop or desktop |
| Operating system | Multiple choice | Android, iPhone (iOS), Windows, macOS, Other |
| Browser | Multiple choice | Chrome, Safari, Edge, Firefox, Other |
| Language you mostly used in the app | Multiple choice | English, Kinyarwanda, Both |

### Section 3 — Tasks
Five questions, *Multiple choice*, options **Yes, without help / Yes, with some help / No**:

- `Task 1. Open the app, read the notice and continue`
- `Task 2. Ask what to feed a 9-month-old baby`
- `Task 3. Switch to Kinyarwanda and ask a question in Kinyarwanda`
- `Task 4. Make a 7-day meal plan for a 12-month-old who must not eat eggs, and download it`
- `Task 5. Ask what to do when a baby has a fever and is very sleepy`

### Section 4 — Your opinion of the app (System Usability Scale)
Ten questions, *Linear scale* from **1 (Strongly disagree)** to **5 (Strongly agree)**, all required.
Keep the `SUS n.` prefix in each title.

| Title | Kinyarwanda (optional, add to the description of each question) |
|---|---|
| `SUS 1. I think that I would like to use NutriAssist-RW frequently.` | Ndatekereza ko nakwifuza gukoresha NutriAssist-RW kenshi. |
| `SUS 2. I found NutriAssist-RW unnecessarily complex.` | Nasanze NutriAssist-RW igoye bitari ngombwa. |
| `SUS 3. I thought NutriAssist-RW was easy to use.` | Nasanze NutriAssist-RW yoroshye gukoresha. |
| `SUS 4. I think that I would need the support of a technical person to be able to use NutriAssist-RW.` | Ndatekereza ko nakenera ubufasha bw'umuntu uzi ikoranabuhanga kugira ngo nshobore gukoresha NutriAssist-RW. |
| `SUS 5. I found the various functions in NutriAssist-RW were well integrated.` | Nasanze ibice bitandukanye bya NutriAssist-RW bihuye neza. |
| `SUS 6. I thought there was too much inconsistency in NutriAssist-RW.` | Nasanze muri NutriAssist-RW harimo ibintu byinshi bidahuye. |
| `SUS 7. I would imagine that most people would learn to use NutriAssist-RW very quickly.` | Ndibwira ko abantu benshi bakwiga gukoresha NutriAssist-RW vuba cyane. |
| `SUS 8. I found NutriAssist-RW very cumbersome to use.` | Nasanze NutriAssist-RW iruhije cyane kuyikoresha. |
| `SUS 9. I felt very confident using NutriAssist-RW.` | Numvise nizeye cyane igihe nakoreshaga NutriAssist-RW. |
| `SUS 10. I needed to learn a lot of things before I could get going with NutriAssist-RW.` | Nakeneye kwiga ibintu byinshi mbere yo gutangira gukoresha NutriAssist-RW. |

Scale labels in Kinyarwanda, if wanted: 1 = *Simbyemera na gato*, 5 = *Ndabyemera cyane*.
(The Kinyarwanda wording is a draft for the native-speaker author to check.)

### Section 5 — Your comments
| Question | Type |
|---|---|
| How useful were the answers for caring for a young child? | Linear scale 1 (not useful) – 5 (very useful) |
| Would you trust the advice enough to act on it? | Multiple choice: Yes / Only after checking with a health worker / No |
| What did you like most? | Paragraph |
| What was difficult or confusing? | Paragraph |
| What should be improved? | Paragraph |

## How the score is computed

Each SUS answer is 1–5. Odd questions (positive statements) count `answer − 1`, even questions
(negative statements) count `5 − answer`; the sum (0–40) × 2.5 gives a score from 0 to 100 per tester,
and the app's score is the mean. It is not a percentage. Interpretation (Bangor, Kortum & Miller, 2009):
68 is average; 71–80 is good; above 80.3 is excellent (grade A); below 51 is poor.
