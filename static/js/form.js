document.addEventListener("DOMContentLoaded", () => {
    const tpl  = document.querySelector("#row-template");
    const rows = document.querySelector("#rows");
    const add  = document.getElementById("add-row");
  
    // 行追加ボタン
    add.addEventListener("click", () => {
        const idx   = rows.querySelectorAll('input[type="file"][name^="receipt"]').length;
        const clone = tpl.innerHTML.replace(/__IDX__/g, idx);
        rows.insertAdjacentHTML("beforeend", clone);
      });      
  
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
  