"""Streamlit UI for DocMind — upload docs, ask questions (streamed or not),
see citations, confidence, contradictions, cache hits, and per-query cost."""
import json
import uuid

import requests
import streamlit as st

API = "http://localhost:8000/api"

st.set_page_config(page_title="DocMind", page_icon="🧠", layout="wide")
st.title("🧠 DocMind — Agentic Document Intelligence")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

with st.sidebar:
    st.subheader("Upload documents")
    files = st.file_uploader(
        "PDF, DOCX, PPTX, TXT, MD, CSV, HTML, JSON",
        accept_multiple_files=True,
    )
    if files and st.button("Ingest"):
        for f in files:
            resp = requests.post(f"{API}/ingest", files={"file": (f.name, f.getvalue())})
            if resp.ok:
                st.success(f"{f.name}: {resp.json()['chunks_indexed']} chunks indexed")
            else:
                st.error(f"{f.name}: {resp.text}")

    st.divider()
    st.subheader("Manage index")
    filename_to_delete = st.text_input("Delete a document by filename")
    if st.button("Delete") and filename_to_delete:
        resp = requests.delete(f"{API}/documents/{filename_to_delete}")
        if resp.ok:
            st.success(f"Deleted {resp.json()['chunks_deleted']} chunks")
        else:
            st.error(resp.text)

    if st.button("Reset entire index + cache"):
        requests.post(f"{API}/reset")
        st.info("Index and cache cleared")

    st.divider()
    st.caption(f"Session: `{st.session_state.session_id}` (conversation memory scoped to this session)")
    if st.button("Clear conversation memory"):
        requests.post(f"{API}/session/{st.session_state.session_id}/clear")
        st.info("Conversation memory cleared")

    st.divider()
    stream_mode = st.toggle("Stream response", value=True)
    cache_stats = requests.get(f"{API}/cache/stats").json() if st.button("Refresh cache stats") else None
    if cache_stats:
        st.caption(f"Semantic cache: {cache_stats['entries']} entries, {cache_stats['total_hits']} hits")

query = st.text_input("Ask a question about your documents")

if query:
    payload = {"query": query, "session_id": st.session_state.session_id}

    if stream_mode:
        placeholder = st.empty()
        full_text = ""
        final_data = None
        with requests.post(f"{API}/query/stream", json=payload, stream=True) as resp:
            for line in resp.iter_lines():
                if not line or not line.startswith(b"data: "):
                    continue
                event = json.loads(line[len(b"data: "):])
                if event["type"] == "delta":
                    full_text += event["text"]
                    placeholder.markdown(full_text)
                elif event["type"] == "final":
                    final_data = event
        data = {**(final_data or {}), "answer": full_text}
    else:
        resp = requests.post(f"{API}/query", json=payload)
        data = resp.json() if resp.ok else None
        if data:
            st.markdown("### Answer")
            st.write(data["answer"])

    if data:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Confidence", f"{data.get('confidence', 0)*100:.0f}%")
        with col2:
            cost = data.get("trace", {}).get("total_cost_usd", 0)
            st.metric("Cost (this query)", f"${cost:.5f}")
        with col3:
            model_label = data.get("model_used") or ("cached" if data.get("from_cache") else "n/a")
            st.metric("Model used", model_label)

        if data.get("from_cache"):
            st.info("⚡ Served from semantic cache — no retrieval or generation call was made.")

        if data.get("sources"):
            st.markdown("### Sources")
            for s in data["sources"]:
                st.caption(f"📄 {s['source']} — {s['location']}")

        if data.get("flagged_claims"):
            with st.expander("⚠️ Flagged claims (low citation support)"):
                for f in data["flagged_claims"]:
                    st.write(f"- {f['sentence']} (overlap: {f['overlap']})")

        if data.get("contradictions"):
            with st.expander("🔀 Possible contradictions between sources"):
                for c in data["contradictions"]:
                    st.write(f"- **{c['chunk_a']['source']}** ({c['chunk_a']['location']}) vs "
                              f"**{c['chunk_b']['source']}** ({c['chunk_b']['location']}): {c['reason']}")

        if data.get("trace"):
            with st.expander("🔍 Pipeline trace (observability)"):
                st.json(data["trace"])
