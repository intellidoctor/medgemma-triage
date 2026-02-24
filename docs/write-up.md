### Project name

MedGemma Triage Assistant -- Agentic Clinical Intake for Brazilian Emergency Rooms

### Your team

Our team consists of three AI engineers: Roberto Shimizu, Thiago Porto, and Roberta Garcia. All work was coauthored with Claude Code (Sonnet 4.6 and Opus 4.6). 
**Roberto Shimizu** set up the github and slack mcps, designed the project's architecture, built the MedGemma model layer on Vertex AI, and built the medical image analysis agent (MedGemma 4B), establishing the project's foundation and architecture. **Thiago Porto** developed the Manchester Protocol triage classifier -- the core clinical reasoning agent -- and wrote end-to-end integration tests validating the full pipeline, also built a conversational intake agent designed for future integration. **Roberta Garcia** built the Streamlit dashboard, the FHIR R4 documentation generator, and the LangGraph orchestrator connecting all agents, plus language support (EN/PT), additional test cases, demo video, and writeup.     

More of our work at [intellidoctor.ai](https://www.intellidoctor.ai).

### Problem statement

**Three converging crises in Brazil's emergency rooms demand a new approach to triage.**

Brazil's SUS (Sistema Unico de Saúde) is the largest public health system in the world, serving over 200 million people, with approximately 75% relying on it exclusively [1]. A single UPA (Emergency Care Unit) sees roughly 300 patients per day, of which approximately 210 are classified as low-acuity (green) [2]. There are 446+ UPAs across all Brazilian regions [3]. This overcrowding "reduces the quality of care, worsens the work environment, increases the time necessary to initiate appropriate patient treatment, and raises the cost of the healthcare system" [2]. Green-category patients wait an average of 4 hours -- twice the time recommended by the Manchester Triage System (MTS).

The Manchester Protocol, while widely adopted in Brazil, has documented limitations. Undertriage is most frequent in orange-level (high urgency) patients, occurring in 27% of cases -- meaning patients who need rapid attention are downgraded, risking dangerous treatment delays [4]. The MTS also performs worse in older patients, with inferior predictive ability for in-hospital mortality [5]. These problems are compounded in SUS, where nurses face work overload performing risk classification and the protocol in high stress environments.


**Impact potential.** If one nurse sees 100 patients per shift, spending 5 minutes on intake plus 2 minutes documenting each (700 min total), AI-assisted intake (saving ~2 min) and auto-generated FHIR documentation (saving ~1.5 min) would free 350 minutes per shift—equivalent to triaging 50 additional patients. Across 446 UPAs (one nurse-shift per UPA), triaged patients per day would rise from 44,600 to 66,900, a 50% increase. Recent systematic reviews support this direction: AI triage systems have demonstrated improved patient prioritization, reduced wait times, and optimized resource allocation in emergency departments [6][7].

### Overall solution

**An agentic triage copilot that uses MedGemma to its fullest potential -- multimodal reasoning, medical domain expertise, and multilingual support.**

We built an agent pipeline orchestrated by LangGraph, where each agent leverages a specific MedGemma capability:

1. **Collect Patient Data** -- Nurse enters patient detials such as chief complaint, symptoms, history, and vital signs into a standardized patient record.

2. **Image Reader (MedGemma 4B multimodal)** -- Analyzes medical images when provided, producing structured clinical findings. MedGemma 4B was specifically pre-trained on medical imaging data including dermatology, radiology, and pathology -- a capability absent in general vision models.

3. **Triage Classifier (MedGemma 27B Text)** -- Applies Manchester Protocol discriminators to the collected patient data, extracting chief complaint, symptoms, history, and vital signs into a standardized patient,  and classifies urgency into Red/Orange/Yellow/Green/Blue. The model outputs structured JSON with `triage_color`, `reasoning`, and `key_discriminators` fields, making every decision auditable. MedGemma's medical reasoning outperforms general models on clinical classification tasks because it understands discriminator semantics (e.g., why "severe pain 8-10/10" maps to Orange, not Yellow).

4. **Returning the FHIR R4 Bundle** -- Along with the triage classifier the system outputs a FHIR R4 Bundle (Patient, Encounter, Observation, Condition). This output aligns with Brazil's RNDS (Rede Nacional de Dados em Saude), the national FHIR-based health data platform with 1.4B+ vaccine registries [8].

**Why MedGemma over general-purpose models?** This application requires medical domain knowledge that general LLMs lack: medical image interpretation, symptom interpretation, and triage protocol reasoning. MedGemma's medical pre-training is the reason the pipeline produces clinically meaningful output. On MedQA (USMLE-style questions), MedGemma 27B scores 87.7% versus 74.9% for the base Gemma 3 27B -- a +12.8 point gain from medical training alone, same architecture [10]. On clinical interview simulations (AgentClinic-MedQA), MedGemma 27B scores 56.2%, exceeding the human physician baseline of 54.0% [10]. For medical imaging, MedGemma 4B outperforms models 7x its size: on out-of-distribution chest X-ray classification (CXR14), it achieves 50.1 macro F1 versus 31.4 for Gemma 3 27B and 39.2 for Gemini 2.5 Pro [10]. MedGemma has also been evaluated on FHIR-formatted clinical records reaching 93.6% accuracy on EHR question answering -- directly relevant to our application [10]. The underlying Gemma 3 architecture provides multilingual capability, which we leverage for Portuguese clinical workflows serving SUS's Portuguese-speaking population. As we continue to develop this system -- adding more clinical specialties, expanding to to support pediatric-specific triage protocols, and potentially fine-tuning on Brazilian clinical data -- having a medically pre-trained foundation becomes even more critical: MedGemma's architecture supports supervised fine-tuning and reinforcement learning, meaning every improvement compounds on top of medical knowledge rather than starting from a general-purpose baseline [10].

**Why LangGraph for orchestration?** LangGraph provides two properties critical for clinical AI: (a) Capability to easily integrate human-in-the-loop checkpoints where the nurse can approve or override the AI suggestion before it becomes final, and (b) full auditability -- every agent's input and output is captured in the state graph, enabling post-hoc review of any triage decision. The nurse retains full clinical authority at all times.

### Technical details

**Architecture.** The application is built in Python 3.12 with a clear separation of concerns:

- `src/agents/` -- One file per agent (image_reader, triage, documentation), each with a single public function
- `src/models/medgemma.py` -- Centralized model interface; agents never call models directly. Uses the OpenAI SDK pointed at Vertex AI dedicated endpoints with GCP bearer token authentication
- `src/pipeline/orchestrator.py` -- LangGraph `StateGraph` connecting agents with conditional routing (skips image analysis if no image is provided)
- `src/fhir/builder.py` -- FHIR R4 Bundle construction using the `fhir.resources` library with LOINC-coded vital signs observations
- `src/ui/app.py` -- Streamlit dashboard with bilingual (EN/PT) support

**Model deployment.** MedGemma 27B Text and MedGemma 4B are deployed as Vertex AI dedicated endpoints. The application authenticates via base64-encoded GCP service account credentials and uses synchronous inference calls.

**FHIR output and RNDS alignment.** Every triage encounter produces a standards-compliant FHIR R4 Bundle containing: Patient resource, Encounter (emergency visit), Observation (Manchester triage classification with vital signs as LOINC-coded components), and Condition (chief complaint mapped to clinical terminology). Brazil's RNDS mandates FHIR as the national health data standard [8]. Our FHIR output is designed for direct integration with RNDS via its RESTful APIs.

**Deployment considerations.** Many Brazilian municipalities face infrastructure challenges including connectivity and equipment limitations. Our architecture addresses this through: lightweight FHIR bundle generation that can work offline and sync when connected, a Streamlit UI that runs on minimal hardware, and MedGemma's relatively compact model sizes (4B for imaging, 27B for text) which can be deployed on-premises or at the edge. Portuguese language support is built into every agent prompt.

**Test suite.** The codebase includes a pytest suite covering agents, pipeline orchestration, and end-to-end triage flows. All model calls are mocked in unit tests via a shared `conftest.py` fixture, ensuring reproducibility without cloud credentials.

**Code.** Source code: [github.com/intellidoctor/medgemma-triage](https://github.com/intellidoctor/medgemma-triage)

---

**References**

[1] Donida, da Costa & Scherer (2021). "COVID-19 as a driver for digital health strategies in Brazil." Frontiers in Public Health. https://pmc.ncbi.nlm.nih.gov/articles/PMC8244723/

[2] Amorim, Ferreira et al. (2019). "Reducing overcrowding in an emergency department." Revista da Associacao Medica Brasileira. https://www.scielo.br/j/ramb/a/svtRwstmQrmDnZwkkjDyL4Q/?lang=en

[3] O'Dwyer et al. (2017). "The current scenario of emergency care policies in Brazil." BMC Health Services Research. https://pmc.ncbi.nlm.nih.gov/articles/PMC5718113/

[4] Souza et al. (2018). "Reliability analysis of the Manchester Triage System." Revista Latino-Americana de Enfermagem. https://www.scielo.br/j/rlae/a/VjS9jL9YLWGs9srC68yRPDf/

[5] Brouns et al. (2019). "Performance of the Manchester triage system in older emergency department patients." Age and Ageing. https://pmc.ncbi.nlm.nih.gov/articles/PMC6322327/

[6] "Clinical Impact of AI-Based Triage: Systematic Review" (2025). PMC. https://pmc.ncbi.nlm.nih.gov/articles/PMC12241827/

[7] Da'Costa et al. (2025). "AI-driven triage in emergency departments: a narrative review." International Journal of Medical Informatics. https://www.sciencedirect.com/science/article/pii/S1386505625000553

[8] de Faria Leao et al. (2024). "Brazilian international patient summary initiative." Oxford Open Digital Health. https://academic.oup.com/oodh/article/doi/10.1093/oodh/oqae015/7667343

[9] Zaboli et al. (2025). "Reproducibility of MTS: multicentre vignette study." Emergency Medicine Journal. https://pubmed.ncbi.nlm.nih.gov/40050005/

[10] Yang et al. (2025). "MedGemma: Medical AI Models." arXiv:2507.05201v3. https://arxiv.org/abs/2507.05201
