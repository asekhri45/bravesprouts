function fitGettingStartedContent() {
  const page = document.getElementById("gettingStartedPage");
  const stage = document.getElementById("gettingStartedScaleStage");

  if (!page || !stage) return;

  const baseWidth = 1500;
  const baseHeight = 900;

  const availableWidth = page.clientWidth;
  const availableHeight = page.clientHeight;

  const scale = Math.min(
    availableWidth / baseWidth,
    availableHeight / baseHeight,
    1
  );

  stage.style.transform = `scale(${scale})`;
  stage.style.left = `${(availableWidth - baseWidth * scale) / 2}px`;
  stage.style.top = `${(availableHeight - baseHeight * scale) / 2}px`;
}

window.addEventListener("resize", fitGettingStartedContent);
window.addEventListener("load", fitGettingStartedContent);

requestAnimationFrame(fitGettingStartedContent);