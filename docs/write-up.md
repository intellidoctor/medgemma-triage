### Project name

MedGemma Triage Assistant -- Agentic Clinical Intake for Brazilian Emergency Rooms

### Your team

[Name your team members, their speciality and the role they played.]

### Problem statement

**Three converging crises in Brazil's emergency rooms demand a new approach to triage.**

Brazil's SUS (Sistema Unico de Saude) is the largest public health system in the world, serving over 200 million people, with approximately 75% relying on it exclusively [1]. A single UPA (Emergency Care Unit) sees roughly 300 patients per day, of which approximately 210 are classified as low-acuity (green) [2]. There are 446+ UPAs across all Brazilian regions [3]. This overcrowding "reduces the quality of care, worsens the work environment, increases the time necessary to initiate appropriate patient treatment, and raises the cost of the healthcare system" [2]. Green-category patients wait an average of 4 hours -- twice the time recommended by the Manchester Triage System (MTS).

The Manchester Protocol, while widely adopted in Brazil, has documented limitations. Undertriage is most frequent in orange-level (high urgency) patients, occurring in 27% of cases -- meaning patients who need rapid attention are downgraded, risking dangerous treatment delays [4]. The MTS also performs worse in older patients, with inferior predictive ability for in-hospital mortality [5]. These problems are compounded in SUS, where nurses face work overload performing risk classification and the protocol, designed for European healthcare contexts, requires adaptation for Brazilian populations [6].

**Impact potential.** If 1 nurse sees 100 patients per shift and spends 5 minutes on intake plus 2 minutes documenting each (700 min total), AI-assisted intake (saving ~2 min) and auto-generated FHIR documentation (saving ~1.5 min) would free 350 minutes per shift -- equivalent to triaging 50 additional patients. Across Brazil's 446+ UPAs, that translates to over 22,000 additional patients triaged daily. Recent systematic reviews support this direction: AI triage systems have demonstrated improved patient prioritization, reduced wait times, and optimized resource allocation in emergency departments [7][8].

### Overall solution

**An agentic triage copilot that uses MedGemma to its fullest potential -- multimodal reasoning, medical domain expertise, and multilingual support -- in a workflow where no single general-purpose model could match its performance.**

We built a four-agent pipeline orchestrated by LangGraph, where each agent leverages a specific MedGemma capability:

1. **Intake Interviewer (MedGemma 27B Text)** -- Conducts a structured clinical interview in Portuguese or English, extracting chief complaint, symptoms, history, and vital signs into a standardized patient record. MedGemma's medical training enables clinically appropriate follow-up questions that a general-purpose LLM would miss (e.g., asking about diaphoresis when chest pain is reported).

2. **Image Reader (MedGemma 4B multimodal)** -- Analyzes medical images (wounds, rashes, imaging) when provided, producing structured clinical findings. MedGemma 4B was specifically pre-trained on medical imaging data including dermatology, radiology, and pathology -- a capability absent in general vision models.

3. **Triage Classifier (MedGemma 27B Text)** -- Applies Manchester Protocol discriminators to the collected evidence and classifies urgency into Red/Orange/Yellow/Green/Blue. The model outputs structured JSON with `triage_color`, `reasoning`, and `key_discriminators` fields, making every decision auditable. MedGemma's medical reasoning outperforms general models on clinical classification tasks because it understands discriminator semantics (e.g., why "severe pain 8-10/10" maps to Orange, not Yellow).

4. **Documentation Generator (MedGemma 27B Text)** -- Produces a FHIR R4 Bundle (Patient, Encounter, Observations, Condition, RiskAssessment) and a clinical handoff note. This output aligns with Brazil's RNDS (Rede Nacional de Dados em Saude), the national FHIR-based health data platform with 1.4B+ vaccine registries [9].

**Why MedGemma over general-purpose models?** Each agent requires medical domain knowledge that general LLMs lack: clinical interview patterns, medical image interpretation, triage protocol reasoning, and FHIR-compliant clinical documentation. MedGemma's medical pre-training is not a nice-to-have -- it is the reason the pipeline produces clinically meaningful output. Additionally, MedGemma supports Portuguese, which is essential for a system serving SUS's Portuguese-speaking population.

**Why LangGraph for orchestration?** LangGraph provides two properties critical for clinical AI: (a) human-in-the-loop checkpoints where the nurse can approve or override the AI suggestion before it becomes final, and (b) full auditability -- every agent's input and output is captured in the state graph, enabling post-hoc review of any triage decision. The nurse retains full clinical authority at all times.

### Technical details

**Architecture.** The application is built in Python 3.12 with a clear separation of concerns:

- `src/agents/` -- One file per agent (intake, image_reader, triage, documentation), each with a single public function
- `src/models/medgemma.py` -- Centralized model interface; agents never call models directly. Uses the OpenAI SDK pointed at Vertex AI dedicated endpoints with GCP bearer token authentication
- `src/pipeline/orchestrator.py` -- LangGraph `StateGraph` connecting agents with conditional routing (skips image analysis if no image is provided)
- `src/fhir/builder.py` -- FHIR R4 Bundle construction using the `fhir.resources` library with LOINC-coded vital signs observations
- `src/ui/app.py` -- Streamlit dashboard with bilingual (EN/PT) support

**Model deployment.** MedGemma 27B Text and MedGemma 4B are deployed as Vertex AI dedicated endpoints. The application authenticates via base64-encoded GCP service account credentials and uses synchronous inference calls.

**FHIR output and RNDS alignment.** Every triage encounter produces a standards-compliant FHIR R4 Bundle containing: Patient resource, Encounter (emergency visit), Observations (vital signs with LOINC codes), Condition (chief complaint mapped to clinical terminology), and RiskAssessment (Manchester triage classification). Brazil's RNDS mandates FHIR as the national health data standard [9]. Our FHIR output is designed for direct integration with RNDS via its RESTful APIs.

**Performance analysis.** We validated the triage classifier against 6 synthetic test cases (3 English, 3 Portuguese) covering chest pain with cardiac risk factors (expected Red/Orange), pediatric fever with respiratory distress (expected Orange/Yellow), and ankle sprain (expected Green). [TODO: insert concordance results]. The system exposes its reasoning chain and key discriminators for every classification, enabling clinical audit. For context, human nurse agreement on MTS classifications yields a Cohen's kappa of 0.59 with a 28.6% error rate [10].

**Deployment considerations.** Many Brazilian municipalities face infrastructure challenges including connectivity and equipment limitations. Our architecture addresses this through: lightweight FHIR bundle generation that can work offline and sync when connected, a Streamlit UI that runs on minimal hardware, and MedGemma's relatively compact model sizes (4B for imaging, 27B for text) which can be deployed on-premises or at the edge. Portuguese language support is built into every agent prompt.

**Test suite.** The codebase includes a comprehensive pytest suite covering agents, pipeline orchestration, and FHIR resource generation. All model calls are mocked in unit tests via a shared test fixture, ensuring reproducibility without cloud credentials.

**Code.** Source code: [github.com/intellidoctor/medgemma-triage](https://github.com/intellidoctor/medgemma-triage)

---

**References**

[1] Donida, da Costa & Scherer (2021). "COVID-19 as a driver for digital health strategies in Brazil." Frontiers in Public Health. https://pmc.ncbi.nlm.nih.gov/articles/PMC8244723/

[2] Amorim, Ferreira et al. (2019). "Reducing overcrowding in an emergency department." Revista da Associacao Medica Brasileira. https://www.scielo.br/j/ramb/a/svtRwstmQrmDnZwkkjDyL4Q/?lang=en

[3] O'Dwyer et al. (2017). "The current scenario of emergency care policies in Brazil." BMC Health Services Research. https://pmc.ncbi.nlm.nih.gov/articles/PMC5718113/

[4] Souza et al. (2018). "Reliability analysis of the Manchester Triage System." Revista Latino-Americana de Enfermagem. https://www.scielo.br/j/rlae/a/VjS9jL9YLWGs9srC68yRPDf/

[5] Brouns et al. (2019). "Performance of the Manchester triage system in older emergency department patients." Age and Ageing. https://pmc.ncbi.nlm.nih.gov/articles/PMC6322327/

[6] Moreira, Tibães, Batista, Cardoso & Brito (2015). "Manchester Triage in Primary Health Care: Ambiguities and Challenges." Texto & Contexto - Enfermagem. https://www.scielo.br/j/tce/a/FtRpkGgTBYSFn4Bj7J5VYvn/

[7] "Clinical Impact of AI-Based Triage: Systematic Review" (2025). PMC. https://pmc.ncbi.nlm.nih.gov/articles/PMC12241827/

[8] Da'Costa et al. (2025). "AI-driven triage in emergency departments: a narrative review." International Journal of Medical Informatics. https://www.sciencedirect.com/science/article/pii/S1386505625000553

[9] de Faria Leao et al. (2024). "Brazilian international patient summary initiative." Oxford Open Digital Health. https://academic.oup.com/oodh/article/doi/10.1093/oodh/oqae015/7667343

[10] Zaboli et al. (2025). "Reproducibility of MTS: multicentre vignette study." Emergency Medicine Journal. https://pubmed.ncbi.nlm.nih.gov/40050005/
