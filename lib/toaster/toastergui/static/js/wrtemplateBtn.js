"use strict";

/* ### WIND_RIVER_EXTENSION_BEGIN */
function wrtemplateBtnsInit() {

  /* Remove any current bindings to avoid duplicated binds */
  $(".wrtemplatebtn").unbind('click');

  $(".wrtemplatebtn").click(function (){
    var wrtObj = $(this).data("wrtemplate");
    var add = ($(this).data('directive') === "add");
    var thisBtn = $(this);

    libtoaster.addRmWRTemplate(wrtObj, add, function (){

      /* In-cell notification */
      var notification = $('<div id="temp-inline-notify" style="display: none; font-size: 11px; line-height: 1.3;" class="tooltip-inner"></div>');
      thisBtn.parent().append(notification);

      if (add){
        notification.text("1 Wind River template added");

        /* Adding a template we only handle the one button */
        thisBtn.fadeOut(function(){
          notification.fadeIn().delay(500).fadeOut(function(){
            $(".wrtemplate-remove-" + wrtObj.id).fadeIn();
            notification.remove();
          });
        });
      } else {
        notification.text("1 Wind River template removed");
        /* Deleting a template we only handle the one button */
        thisBtn.fadeOut(function(){
          notification.fadeIn().delay(500).fadeOut(function(){
            $(".wrtemplate-add-" + wrtObj.id).fadeIn();
            notification.remove();
          });
        });
      }

    });

  });
}
/* ### WIND_RIVER_EXTENSION_END */

