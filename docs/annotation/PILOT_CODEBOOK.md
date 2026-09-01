# Pilot Annotation Codebook — Citation-Context Reception

**Project:** Limits-to-Growth reception study (Papers A and B). **Stage:** 87-item pilot prepared; human labeling not started. **Version:** 0.2 (pre-pilot; revised after the pilot round, then pre-registered before the main round).

This codebook tells you how to label each citation context on three independent axes: **function**, **stance**, and **depth**. Read it once in full before starting. During the pilot, flag anything ambiguous and note where the rules are unclear — the pilot exists to find those gaps before we commit to the full set.

---

## 1. What we annotate, and what we do not

You are labeling a single **citation context**: one place where a citing work refers to one of the three seed works (Meadows et al. 1972, *The Limits to Growth*; Commoner 1971, *The Closing Circle*; Schumacher 1974, *Small Is Beautiful*).

Each label is a judgment about **how this citing passage uses, evaluates, and engages the seed** — nothing more. Specifically, do not label:

- the overall quality or importance of the citing work;
- the topic of the citing work;
- whether the seed's claims are correct in reality;
- your own view of the seed.

Only the relationship expressed in the passage in front of you matters.

---

## 2. The unit

Each item shows three explicit fields: the sentence immediately **before** the
citation, the **citing sentence**, and the sentence immediately **after** the
citation. The combined `context` column repeats those three sentences for
convenient reading. Every pilot item has all three sentences; incomplete
document-edge windows, S2-only pre-computed snippets, likely reference-list
entries, and unattributed title-phrase matches were excluded before sampling.

The item also shows the **seed**, publication year, and **work type**. Work type
means the citing record's OpenAlex publication format, such as `article`,
`book-chapter`, `dissertation`, `review`, or `preprint`; it is not a judgment
about citation function or research method. If a citing work refers to the seed
in several distinct body-text places, each place is a separate item. Label only
the seed named in the item, even if the passage cites other works too.

---

## 3. How to annotate

Read the full window, then assign one label on each of the three axes, in this order: function, stance, depth. The axes are **independent** — any combination is possible (for example, a passage can be CompareContrast, negative, and substantive at once). Use the **flag** field for items you cannot label confidently, and the **notes** field to record a second-choice label or a short reason whenever you hesitate. In the pilot, err toward flagging and noting; that signal is what we use to improve the codebook.

---

## 4. Axis A — Citation function

What role does the seed play in this passage? Assign exactly one class. When more than one could apply, work down this decision order and take the first that fits:

1. **Uses** — the citing work uses the seed's method, model, data, or definitions.
2. **Extends** — the citing work modifies, adds to, or builds on the seed's method, model, or data.
3. **CompareContrast** — the citing work compares or contrasts its own results, assumptions, or position with the seed's, or agrees/disagrees with it.
4. **Motivation** — the seed motivates the citing work's problem or shows the need for it.
5. **Future** — the seed is named as a direction for future work.
6. **Background** — none of the above; the seed is general context or prior literature. This is the default.

| Class | Use when | Illustrative passage (constructed) |
|---|---|---|
| Background | the seed is part of the general literature being invoked | "Concerns about the sustainability of exponential growth have a long history (Meadows et al. 1972; Commoner 1971)." |
| Motivation | the seed establishes the problem the citing work addresses | "The prospect of resource-driven collapse raised by Meadows et al. (1972) motivates our re-examination of long-run mineral supply." |
| Uses | the citing work applies the seed's method/model/data | "We adopt the system-dynamics approach of Meadows et al. (1972) to simulate regional water demand." |
| Extends | the citing work changes or builds on the seed's method/model | "We extend the World3 model of Meadows et al. (1972) with an endogenous technological-change sector." |
| CompareContrast | the citing work positions its results/assumptions against the seed's | "Unlike the overshoot trajectory of Meadows et al. (1972), our scenarios stabilize under moderate efficiency gains." |
| Future | the seed is flagged as a next step | "A natural next step is to revisit the World3 scenarios of Meadows et al. (1972) with updated planetary-boundary data." |

**Common confusions.** Background vs Motivation: Background is a passing nod to the literature; Motivation means the seed specifically sets up the citing work's aim. Uses vs Extends: Uses applies the seed as-is; Extends modifies it. Extends vs CompareContrast: if the citing work builds on the seed, Extends; if it sets its results or assumptions against the seed, CompareContrast. When a passage both builds on and contrasts, the decision order puts Extends first only if the building-on is the salient act; if the passage's point is the contrast, choose CompareContrast and note the alternative.

---

## 5. Axis B — Stance toward the seed

Does the citing author evaluate the seed positively, negatively, or neither? Assign one class. Stance is about **the citing author's own position on the seed**, not the citing work's general tone and not criticism the author merely reports.

| Class | Use when | Illustrative passage (constructed) |
|---|---|---|
| Positive | the author endorses, supports, or affirms the seed's claims or value | "Meadows et al. (1972) correctly identified the tension between growth and finite resources." |
| Neutral | the author invokes the seed without evaluating it | "Meadows et al. (1972) modeled interactions among population, capital, and resources." |
| Negative | the author disputes, criticizes, or identifies flaws in the seed | "The collapse predictions of Meadows et al. (1972) rested on implausibly static assumptions about substitution." |

Expect **neutral to dominate** — most citations are not evaluative. That is normal and is reported, not corrected for.

**Reported vs held criticism.** Code the citing author's own stance, not criticism they attribute to others. "Although *The Limits to Growth* was widely criticized in the 1970s, its core message has aged well" is **positive**: the author defends the seed and reports the criticism as background. Flag these for review during the pilot.

**Hedged or mixed.** Choose the dominant evaluation. If a passage is genuinely balanced with no dominant side, label neutral and flag it.

---

## 6. Axis C — Engagement depth

Does the passage engage the seed's actual content, or only mention it? Assign one class.

| Class | Use when | Illustrative passage (constructed) |
|---|---|---|
| Perfunctory | the seed is a passing or grouped mention; its specific content is not engaged | "Several early studies warned of ecological limits (e.g., Meadows et al. 1972)." |
| Substantive | the passage engages the seed's specific claims, method, or findings | "Meadows et al. (1972) argued that delays between pollution and its effects produce overshoot; we test this mechanism directly." |

**Depth does not depend on citation count.** A passage that cites only the seed can still be perfunctory if it engages nothing specific ("Environmental concern has grown (Meadows et al. 1972)."). A seed cited within a list can be substantive if the passage discusses its particular contribution. The test: does the passage do anything with the seed's content, or would replacing the seed with any similar reference leave the sentence's meaning intact?

---

## 7. Worked example across all three axes

> "Unlike Meadows et al. (1972), whose World3 model omitted price-mediated substitution, we incorporate adaptive resource pricing and find no collapse."

- **Function: CompareContrast.** The passage's point is to set the citing work's result and assumptions against the seed's. (Extends is a defensible second choice because the work also builds on World3; note it.)
- **Stance: Negative.** The author identifies an omission in the seed.
- **Depth: Substantive.** The seed's specific modeling assumption is engaged.

---

## 8. Difficult cases and flags

- **Too little context to judge.** If the window is truncated or uninformative, flag `insufficient_context` and leave labels blank.
- **Reference-list or source-extraction artifact.** These were screened before
  sampling, but if one remains, flag `not_a_citing_passage` and leave the three
  labels blank.
- **Two plausible classes.** Pick the better fit per the rules and record the alternative in notes. Do not leave it blank.
- **Several seeds or several citations in one window.** Label only the item's named seed; ignore the others for labeling.
- **Non-English passage.** Flag `non_english` and skip unless you read the language comfortably.
- **The seed is cited but the passage is about something else.** If the seed's role is genuinely unclear, label function Background, stance neutral, and flag for discussion.

---

## 9. Pilot procedure

Two annotators label the same 87 contexts **independently**, without discussion.
The pilot exhausts the eligible pool and is not seed-balanced (48 Meadows, 17
Commoner, 22 Schumacher); it is for codebook and reliability testing, not
cross-seed prevalence estimates. Do not confer on specific items during the
round. Flag liberally and use the notes field whenever a rule felt forced —
proposed wording fixes are welcome and expected. After the round we compute
agreement, review every disagreement and flag together, revise this codebook,
and (if needed) run a second short pilot before the main set.

---

## 10. Reliability targets (for transparency)

Agreement is measured per axis and per class with Krippendorff's alpha. Thresholds, fixed in advance: at or above 0.80 supports firm conclusions; 0.667 to 0.80 supports tentative conclusions only; below 0.667 means the axis is revised and re-piloted, or reported as low-reliability. The point of the pilot is to reach the threshold by improving the rules, not by forcing agreement.
