(async () => {
  const LABELS = {
    definition: { keep_trunk: "Keep registered", adopt_branch: "Adopt branch", research: "Needs research" },
    implementation: { keep_trunk: "Accept as is", adopt_branch: "Fix implementation", research: "Needs research" },
    data: { keep_trunk: "Accept caveat", adopt_branch: "Fix the data", research: "Needs research" },
  };
  const panels = [...document.querySelectorAll(".decision[data-branch]")];
  const kindOf = {};
  panels.forEach(p => { kindOf[p.dataset.branch] = p.dataset.kind; });
  const label = (bid, choice) => (LABELS[kindOf[bid] || "definition"] || {})[choice] || choice;
  const sumFor = (bid, text, decided) => document.querySelectorAll("[data-sum-for]").forEach(el => {
    if (el.dataset.sumFor !== bid) return;
    el.textContent = text; el.classList.toggle("c-decided", !!decided); el.classList.toggle("c-open", !decided);
  });
  const currentFor = (bid, node) => document.querySelectorAll("[data-current-for]").forEach(el => {
    if (el.dataset.currentFor !== bid) return;
    el.textContent = ""; el.append(node.cloneNode(true));
  });

  const db = await claude.use("db");
  const user = await claude.use("user");
  if (!db) {
    document.querySelectorAll("[data-current-for]").forEach(el => el.textContent = "Decisions are not available in this view. Open the page signed in to record or see picks.");
    document.querySelectorAll("[data-sum-for]").forEach(el => el.textContent = "unavailable");
    document.querySelectorAll(".decision input, .decision textarea").forEach(el => el.disabled = true);
    return;
  }
  const me = user ? await user.me() : null;
  const canWrite = user ? await user.can("data.write") : null;
  let writable = canWrite !== false && !!(me && me.id);
  const fmtTime = (iso) => { try { return new Date(iso).toLocaleString(); } catch (e) { return iso; } };

  const ids = [...new Set([...panels.map(p => p.dataset.branch),
                           ...[...document.querySelectorAll("[data-follows]")].map(el => el.dataset.follows)])];
  for (const bid of ids) {
    const docRef = db.doc("branches/" + bid);
    docRef.onSnapshot(async (snap) => {
      if (!snap.exists) {
        const t = document.createTextNode("No decision recorded yet.");
        currentFor(bid, t); sumFor(bid, "Not decided", false); return;
      }
      const d = snap.data();
      const ps = user ? await user.profiles([d.by]) : {};
      const who = (ps[d.by] && ps[d.by].name) || "Someone";
      const frag = document.createDocumentFragment();
      const b = document.createElement("b"); b.textContent = label(bid, d.choice);
      frag.append("Current: ", b, " · " + who + " · " + fmtTime(d.at));
      currentFor(bid, frag); sumFor(bid, label(bid, d.choice), true);
      const panel = panels.find(p => p.dataset.branch === bid);
      if (panel && !panel.querySelector("input:checked")) {
        const r = panel.querySelector('input[value="' + d.choice + '"]'); if (r) r.checked = true;
        panel.querySelector(".save").disabled = !writable;
      }
    }, () => currentFor(bid, document.createTextNode("Could not load the saved decision.")));
  }

  for (const panel of panels) {
    const bid = panel.dataset.branch;
    const docRef = db.doc("branches/" + bid);
    const logRef = docRef.collection("log");
    const save = panel.querySelector(".save"), msg = panel.querySelector(".msg"), note = panel.querySelector("textarea"), hist = panel.querySelector(".hist");
    const radios = [...panel.querySelectorAll("input[type=radio]")];
    const enable = () => { save.disabled = !writable || !radios.some(r => r.checked); };
    radios.forEach(r => r.addEventListener("change", enable));
    if (!writable) { radios.forEach(r => r.disabled = true); note.disabled = true; msg.textContent = "You can see decisions here; recording one needs Contributor access."; }

    logRef.orderBy("at", "desc").limit(50).onSnapshot(async (qs) => {
      if (qs.empty) return;
      const who = [...new Set(qs.docs.map(x => x.data().by).filter(Boolean))];
      const ps = user ? await user.profiles(who) : {};
      hist.textContent = "";
      for (const doc of qs.docs) {
        const d = doc.data();
        const li = document.createElement("li");
        const img = document.createElement("img"); img.alt = ""; img.src = ps[d.by] ? ps[d.by].avatarUrl : "";
        const top = document.createElement("div"); const s = document.createElement("b");
        s.textContent = label(bid, d.choice); top.append(s, " · " + ((ps[d.by] && ps[d.by].name) || "Someone"));
        const meta = document.createElement("div"); meta.className = "meta";
        meta.textContent = fmtTime(d.at) + (d.note ? " — " + d.note : "");
        li.append(img, top, meta); hist.append(li);
      }
    }, () => {});

    save.addEventListener("click", async () => {
      const pick = radios.find(r => r.checked);
      if (!pick || !writable) return;
      save.disabled = true; msg.textContent = "Saving…";
      const entry = { choice: pick.value, note: note.value.trim().slice(0, 1000), by: me.id, at: new Date().toISOString(), branch: bid, kind: panel.dataset.kind };
      try {
        await logRef.add(entry);
        await docRef.set(entry);
        msg.textContent = "Saved."; note.value = "";
      } catch (e) {
        if (e && e.code === "invalid_argument") { writable = false; msg.textContent = "Your access level can view decisions but not record them."; }
        else if (e && e.code === "quota_exceeded") { msg.textContent = "The decision store is full; ask the owner to clear old entries."; }
        else { msg.textContent = "Not saved. Try again in a moment."; }
      } finally { enable(); }
    });
  }
})();
