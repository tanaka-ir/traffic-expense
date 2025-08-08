document.addEventListener("DOMContentLoaded", () => {
  const tpl  = document.querySelector("#row-template");
  const rows = document.querySelector("#rows");
  const add  = document.getElementById("add-row");

  /* 行追加ボタン */
  add.addEventListener("click", () => {
    /* 既に存在する file input の “name” を集合で数える */
    const names = new Set(
      Array.from(
        rows.querySelectorAll('input[type="file"][name^="receipt"]')
      ).map(el => el.name)          // 例: "receipt0[]", "receipt1[]"
    );
    const idx = names.size;         // 0,1,2,… と連番になる
    const html  = tpl.innerHTML.replace(/__IDX__/g, idx);
    rows.insertAdjacentHTML("beforeend", html);
  });

  /* 行削除ボタン */
  document.addEventListener("click", ev => {
    if (!ev.target.closest(".delete-row")) return;
    const tr = ev.target.closest("tr[data-row]");
    if (tr) tr.remove();

    // file input の name を振り直す
    rows.querySelectorAll('input[type="file"][name^="receipt"]').forEach((el, i) => {
      el.name = `receipt${i}[]`;
    });
  });

  /* ファイルラベル更新 */
  document.addEventListener("change", ev => {
    if (!ev.target.matches('input[type="file"][name^="receipt"]')) return;
    const info = ev.target.closest("td").querySelector(".file-info");
    const n    = ev.target.files.length;
    info.textContent = n === 0 ? "" : n === 1 ? ev.target.files[0].name : `${n} 枚選択`;
  });

  /* 送信バリデーション */
  document.querySelector("form").addEventListener("submit", ev => {
    const trList = rows.querySelectorAll("tr[data-row]");       // ← ①
    for (const tr of trList) {
      const date = tr.querySelector('input[name="date[]"]')?.value.trim() || "";          // ← ②
      const dpt  = tr.querySelector('input[name="departure[]"]')?.value.trim() || "";
      const dst  = tr.querySelector('input[name="destination[]"]')?.value.trim() || "";
      const amt  = tr.querySelector('input[name="amount[]"]')?.value.trim() || "";
      const hasFile = tr.querySelector('input[type="file"]')?.files.length > 0;

      const anyInput = date || dpt || dst || amt;

      // 空行 → DOM から除去
      if (!anyInput && !hasFile) {
        tr.remove();
        continue;
      }
      // 必須欠落 → エラー
      if (!date || !dpt || !dst || !amt) {
        ev.preventDefault();
        alert("日付・出発・到着・金額は必須です。");
        return;
      }
    }
  });
});
