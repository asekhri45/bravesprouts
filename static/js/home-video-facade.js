/*
  Click-to-load YouTube facade for the homepage video guides section.
  Avoids loading the full YouTube iframe/player payload for every visitor --
  only injects the real embed when a visitor actually clicks to watch.
*/
document.addEventListener("DOMContentLoaded", function () {
  var facades = document.querySelectorAll(".home-youtube-facade");

  facades.forEach(function (button) {
    button.addEventListener("click", function () {
      var videoId = button.getAttribute("data-video-id");
      var title = button.getAttribute("data-video-title") || "YouTube video";

      var iframe = document.createElement("iframe");
      iframe.src = "https://www.youtube.com/embed/" + videoId + "?autoplay=1&rel=0&modestbranding=1";
      iframe.title = title;
      iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
      iframe.referrerPolicy = "strict-origin-when-cross-origin";
      iframe.allowFullscreen = true;
      iframe.className = "home-youtube-embed";

      button.replaceWith(iframe);
    });
  });
});
