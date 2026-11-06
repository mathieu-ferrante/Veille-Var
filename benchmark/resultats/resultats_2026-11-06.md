# Résultats du benchmark – 2026-11-06

| Service | Modèle | JSON conforme (F4) | Exactitude classement (F1) | Écart pertinence (F2) | Résumés en français (F3) | Latence moy. / p95 | Tokens | Coût estimé | Erreurs de service |
|---|---|---|---|---|---|---|---|---|---|
| Mistral AI – La Plateforme | ministral-8b-latest | 100.0 % | 76.7 % | 0.57 | 100.0 % | 2.83 s / 4.23 s | 29010 | 0.0043 € | 0 |
| Google Gemini API | gemini-3.5-flash-lite | 100.0 % | 80.0 % | 0.6 | 100.0 % | 1.2 s / 1.71 s | 29166 | 0.0232 € | 0 |
| Modèle local (Ollama) | gemma3:12b | 100.0 % | 76.7 % | 0.9 | 100.0 % | 26.26 s / 37.34 s | 28680 | 0.0 € | 0 |

Lecture : F4 en pourcentage des réponses reçues ; F1 et F3 en pourcentage des réponses conformes ; F2 = écart absolu moyen entre la note du modèle et l'annotation humaine (0 = parfait). Les erreurs de service (quota, réseau) ne sont pas imputées au modèle. La fidélité des résumés se juge à la relecture des fichiers bruts (`resultats/brut/`).
