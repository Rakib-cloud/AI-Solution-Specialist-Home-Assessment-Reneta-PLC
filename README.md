# Leave Policy Assistant

Part A of the Renata AI Solutions Specialist assessment. An HR assistant that answers employee
questions **using only the uploaded leave policy**, and cites the section every answer came from.

## Run it

Python 3.9 or newer. No API key, no account, no configuration file.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:5050**.

The attached `XYZ Company Leave Policy (Sample).pdf` is already loaded and published, so there is
nothing to upload first. Go to **Assistant**, click the policy chip at the top to select it, and ask.

> No model API key is used. The policy text is read on this computer, so nothing leaves the machine
> and there is no key for you to supply. `.env.example` is optional: copy it only if you want to
> change the port or set your own secret key.

## Check the three requirements

On the **Assistant** page, click the three tags above the message box, or type these:

| Ask this | What should happen |
| --- | --- |
| How many casual leave days do I get in a year? | *Casual Leave: 8 working days per year. It is paid.* — with **Section 4.0** and **Section 4.2** shown as the source |
| Can I take study leave? | exactly `I don't know, please contact HR.`, with no citation |
| How many leave days has Rahim taken? | a polite refusal that points to HR and cites **Section 9**, the confidentiality section |

The tags on that page cover more cases, including *Why is my colleague on medical leave?*. Hover a
tag to see the full question before you send it.

## How it works

The PDF is split into numbered sections and its entitlements table is read separately. A question is
matched against those sections, and the matching sentences are returned with the section number.

Three checks run before any answer reaches the screen:

1. **Citation** — the answer must name a section that exists. No section, no answer.
2. **Figures** — every number in the answer must appear in the policy, so a figure cannot be invented.
3. **Privacy** — a question about another person is refused before any lookup happens.

Two decisions are worth calling out:

- **The subject of a question must be in the policy.** *"Can I take leave for jury duty?"* shares the
  words *leave* and *take* with the document, but *jury duty* is nowhere in it, so the reply is
  `I don't know`.
- **Where the checks disagree, the assistant says it does not know.** A missed answer is cheaper than
  a confident wrong one.

## Tests

```bash
pytest                              # 86 tests
pytest tests/test_requirements.py   # the three required behaviours, 69 questions
```

`tests/test_requirements.py` runs against the attached sample policy: in-policy questions paired with
the section each answer must cite, questions the policy does not cover, and requests for another
employee's data. A failure names the question and what came back, so a wrong citation reads as
`'Who can see my leave records?' cited ['4.3'], expected 9.2`.

## Managing policies

**Policies** lists every policy with its number, version and status, and a search and status filter.
Row icons view, edit, download, publish, hand to the assistant, or delete; publishing and deleting
ask for confirmation first. **Create policy** builds a new one in three steps — pick the template,
fill the header, set the leave types — and the editor opens one section at a time. A new policy is
marked *Not saved yet* until you press **Save draft**.

## Project layout

```
app/routes.py                 upload, policy editor, and questions
app/services/extractor.py     PDF text, sections, and tables
app/services/reader.py        finds the answer in the policy text
app/services/grounded.py      citation, figure, and privacy checks
app/services/authored.py      draft, publish, and section numbering
app/services/pdf_export.py    policy PDF in the sample layout
app/templates/, app/static/   pages, styles, and scripts
tests/test_requirements.py    the three Part A behaviours
run.py                        start the app
```

## Known limitation

The assistant matches the words of a question against the words of the policy; it does not understand
them. Where a question uses vocabulary the policy never uses, it answers `I don't know` even though
the fact is in the document. Synonyms are handled by a small table in `services/reader.py`, which has
to be maintained by hand rather than generalising on its own.

With more time I would replace the matcher with sentence embeddings over the same sections, and keep
the three checks unchanged. They are what make the answers trustworthy, and they do not depend on how
the passages are found.

## Notes

- The sample policy is a dummy document for this assessment. Do not share it outside the assessment,
  and do not upload real employee or company data.
- A scanned PDF with no text layer is rejected. This app reads the text in the file; it does not OCR.
- Uploading a different policy starts a fresh analysis. Earlier questions are not reused as facts.
