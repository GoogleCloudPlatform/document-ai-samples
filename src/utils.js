/**
   * Image an image that is 600x800 (imageWidth x imageHeight)
   * Image a viewport that is 100x100 (viewWidth x viewHeight)
   * What should the image size be?
   * Well, the height of the image should be 100 as that would maximize the image height
   * But what of the width?  It should be 600 x whatever we scaled the height.  The height scalled from 800->100.
   * This is a multiplier of (viewHeight/imageHeight)
   */

/**
 * 
 * @param {*} view - The {width, height} of the view
 * @param {*} image - The {width, height} of the image
 * @returns The new {width, height, x, y}
 */
function imageScale(view, image) {

  let width;
  let height;
  if (image.height > image.width) {
    height = view.height;
    width = image.width * height / image.height

  } else {
    width = view.width;
    height = image.height * width / image.width;
  }
  let x = view.width / 2 - width /2;
  let y = 0;
  return {width: width, height: height, x, y: y}
}

export {imageScale}