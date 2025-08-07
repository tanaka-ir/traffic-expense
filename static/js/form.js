document.addEventListener("DOMContentLoaded", () => {
    const tpl  = document.querySelector("#row-template");
    const rows = document.querySelector("#rows");
    const add  = document.getElementById("add-row");
  
    // 行追加ボタン
    add.addEventListener("click", () => {
      const names = new Set(
        Array.from(rows.querySelectorAll('input[type="file"][name^="receipt"]'))
             .map(el => el.name)   // 例: "receipt0[]", "receipt1[]", ...
      );
      const idx   = names.size;     // 既存の一意な行数 = 次の idx
      const clone = tpl.innerHTML.replace(/__IDX__/g, idx);
      rows.insertAdjacentHTML("beforeend", clone);
    });      

    // ★★【ここから追加①：行削除ボタン】------------------------
    document.addEventListener("click", ev => {
      if (!ev.target.closest(".delete-row")) return; // 他要素は無視
      const tr = ev.target.closest("tr");
      if (tr) tr.remove();

      /* 削除後：現存 file input の name を振り直す */
      const inputs = Array.from(
        rows.querySelectorAll('input[type="file"][name^="receipt"]')
      );
      inputs.forEach((el, i) => {
        el.name = `receipt${i}[]`;
      });
    });
    // ★★【追加①ここまで】--------------------------------------
  
    // ★ ファイル選択時にラベル更新（行追加後も効くよう委譲）
    document.addEventListener("change", (ev) => {
      if (ev.target.matches('input[type="file"][name^="receipt"]')) {
        const files = ev.target.files;
        const info  = ev.target
                        .closest("td")
                        .querySelector(".file-info");
  
        if (!files || files.length === 0) {
          info.textContent = "";                   // 何も選ばれていない
        } else if (files.length === 1) {
          info.textContent = files[0].name;        // 1 枚なら名前を表示
        } else {
          info.textContent = `${files.length} 枚選択`;
        }
      }
    });
  });
  