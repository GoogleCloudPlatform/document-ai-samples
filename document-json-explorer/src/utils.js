/*
# Copyright 2022, Google, Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
*/

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